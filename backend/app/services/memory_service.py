"""Dịch vụ ký ức vectơ - triển khai ký ức dài hạn và truy xuất ngữ nghĩa dựa trên ChromaDB"""
import chromadb
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from app.logger import get_logger
from app.services.onnx_embedding import OnnxEmbeddingModel
import os
import hashlib

logger = get_logger(__name__)

class MemoryService:
    """Dịch vụ quản lý ký ức vectơ - Triển khai truy xuất ngữ nghĩa và ký ức dài hạn"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Chế độ đơn nhất"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """khởi tạoChromaDBvàEmbeddingmô hình"""
        if self._initialized:
            return
            
        try:
            # Đảm bảo thư mục dữ liệu tồn tại
            chroma_dir = "data/chroma_db"
            os.makedirs(chroma_dir, exist_ok=True)
            
            # khởi tạoChromaDBclient(DùngAPI - PersistentClient)
            self.client = chromadb.PersistentClient(path=chroma_dir)
            
            logger.info("🔄 đang tải ONNX Embedding mô hình...")
            self.embedding_model = OnnxEmbeddingModel()
            logger.info(f"✅ ONNX Embedding Tải mô hình thành công: {self.embedding_model.model_dir}")
            
            self._initialized = True
            logger.info("✅ MemoryServiceKhởi tạo thành công")
            logger.info(f"  - ChromaDBthư mục: {chroma_dir}")
            logger.info("  - Embeddingmô hình: paraphrase-multilingual-MiniLM-L12-v2 (ONNX FP32)")
            
        except Exception as e:
            logger.error(f"❌ MemoryServiceKhởi tạo thất bại: {str(e)}")
            raise
    
    def get_collection(self, user_id: str, project_id: str):
        """
        Lấy hoặc tạo tập hợp ký ức của dự án
        
        Mỗi dự án của mỗi người dùng cócollection,độc lập, thực hiện cô lập dữ liệu
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
        
        Returns:
            ChromaDB Collectionđối tượng
        """
        # ChromaDB collectionQuy tắc đặt tên:
        # 1. 3-63ký tự (quan trọng nhất!)
        # 2. Đầu và cuối phải là chữ cái hoặc chữ số
        # 3. Chỉ được chứa chữ cái, chữ số, gạch dưới hoặc gạch ngang
        # 4. Không được chứa dấu chấm liên tiếp(..)
        # 5. Không được làIPv4địa chỉ hợp lệ
        
        # sử dụngSHA256nén bămIDđộ dài, đảm bảo không vượt quá63ký tự
        # định dạng: u_{user_hash}_p_{project_hash} (khoảng30ký tự)
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
        project_hash = hashlib.sha256(project_id.encode()).hexdigest()[:8]
        collection_name = f"u_{user_hash}_p_{project_hash}"
        
        try:
            return self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "user_id": user_id,
                    "project_id": project_id,
                    "created_at": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"❌ lấycollectionthất bại: {str(e)}")
            raise
    
    async def add_memory(
        self,
        user_id: str,
        project_id: str,
        memory_id: str,
        content: str,
        memory_type: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Thêm ký ức vào cơ sở dữ liệu vectơ
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            memory_id: Ký ức duy nhấtID
            content: Nội dung ký ức(sẽ được chuyển thành vectơ)
            memory_type: Loại ký ức
            metadata: Siêu dữ liệu bổ sung
        
        Returns:
            Đã thêm thành công hay chưa
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Tạo biểu diễn vectơ của văn bản
            embedding = self.embedding_model.encode(content).tolist()
            
            # Chuẩn bị siêu dữ liệu(ChromaDBYêu cầu mọi giá trị là kiểu cơ bản)
            chroma_metadata = {
                "memory_type": memory_type,
                "chapter_id": str(metadata.get("chapter_id", "")),
                "chapter_number": int(metadata.get("chapter_number", 0)),
                "importance": float(metadata.get("importance_score", 0.5)),
                "tags": json.dumps(metadata.get("tags", []), ensure_ascii=False),
                "title": str(metadata.get("title", ""))[:200],  # Giới hạn độ dài
                "is_foreshadow": int(metadata.get("is_foreshadow", 0)),
                "created_at": datetime.now().isoformat()
            }
            
            # Thêm thông tin nhân vật liên quan
            if metadata.get("related_characters"):
                chroma_metadata["related_characters"] = json.dumps(
                    metadata["related_characters"], 
                    ensure_ascii=False
                )
            
            # Lưu vào kho vectơ
            collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[chroma_metadata]
            )
            
            logger.info(f"✅ Đã thêm ký ức: {memory_id[:8]}... (loại:{memory_type}, mức quan trọng:{chroma_metadata['importance']})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Thêm ký ức thất bại: {str(e)}")
            return False
    
    async def batch_add_memories(
        self,
        user_id: str,
        project_id: str,
        memories: List[Dict[str, Any]]
    ) -> int:
        """
        Thêm hàng loạt ký ức(hiệu năng tốt hơn)
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            memories: Danh sách ký ức,mỗi mục chứaid, content, type, metadata
        
        Returns:
            Số lượng thêm thành công
        """
        if not memories:
            return 0
            
        try:
            collection = self.get_collection(user_id, project_id)
            
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            # Chuẩn bị dữ liệu hàng loạt
            for mem in memories:
                ids.append(mem['id'])
                documents.append(mem['content'])
                
                # tạoembedding
                embedding = self.embedding_model.encode(mem['content']).tolist()
                embeddings.append(embedding)
                
                # Chuẩn bị siêu dữ liệu
                metadata = mem.get('metadata', {})
                chroma_metadata = {
                    "memory_type": mem['type'],
                    "chapter_id": str(metadata.get("chapter_id", "")),
                    "chapter_number": int(metadata.get("chapter_number", 0)),
                    "importance": float(metadata.get("importance_score", 0.5)),
                    "tags": json.dumps(metadata.get("tags", []), ensure_ascii=False),
                    "title": str(metadata.get("title", ""))[:200],
                    "is_foreshadow": int(metadata.get("is_foreshadow", 0)),
                    "created_at": datetime.now().isoformat()
                }
                metadatas.append(chroma_metadata)
            
            # Thêm hàng loạt
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"✅ Thêm hàng loạt ký ức thành công: {len(memories)}")
            return len(memories)
            
        except Exception as e:
            logger.error(f"❌ Thêm hàng loạt ký ức thất bại: {str(e)}")
            return 0
    
    async def search_memories(
        self,
        user_id: str,
        project_id: str,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
        chapter_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm ngữ nghĩa các ký ức liên quan
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            query: Văn bản truy vấn(sẽ được chuyển thành vectơ để tìm kiếm tương đồng)
            memory_types: Lọc ký ức theo loại cụ thể
            limit: Số lượng kết quả trả về
            min_importance: Ngưỡng quan trọng tối thiểu
            chapter_range: Phạm vi chương (start, end)
        
        Returns:
            Danh sách ký ức liên quan,Sắp xếp theo độ tương đồng
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Tạo vectơ truy vấn
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Xây dựng điều kiện lọc - ChromaDBYêu cầu dùng$andkết hợp nhiều điều kiện
            where_filter = None
            conditions = []
            
            if memory_types:
                conditions.append({"memory_type": {"$in": memory_types}})
            if min_importance > 0:
                conditions.append({"importance": {"$gte": min_importance}})
            if chapter_range:
                conditions.append({"chapter_number": {"$gte": chapter_range[0]}})
                conditions.append({"chapter_number": {"$lte": chapter_range[1]}})
            
            # Chọn định dạng phù hợp theo số lượng điều kiện
            if len(conditions) == 0:
                where_filter = None
            elif len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}
            
            # Thực thi tìm kiếm tương đồng vectơ
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter
            )
            
            # Định dạng kết quả
            memories = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    memories.append({
                        "id": results['ids'][0][i],
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "similarity": 1 - results['distances'][0][i] if 'distances' in results else 1.0,
                        "distance": results['distances'][0][i] if 'distances' in results else 0.0
                    })
            
            logger.info(f"🔍 Tìm kiếm ngữ nghĩa hoàn tất: truy vấn='{query[:30]}...', tìm thấy{len(memories)}ký ức")
            return memories
            
        except Exception as e:
            logger.error(f"❌ Tìm kiếm ký ức thất bại: {str(e)}")
            return []
    
    async def get_recent_memories(
        self,
        user_id: str,
        project_id: str,
        current_chapter: int,
        recent_count: int = 3,
        min_importance: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Lấy ký ức quan trọng của vài chương gần nhất(Dùng để giữ tính liên tục)
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            current_chapter: Số chương hiện tại
            recent_count: Lấy vài chương gần nhất
            min_importance: Ngưỡng quan trọng tối thiểu
        
        Returns:
            Danh sách ký ức của các chương gần đây,Sắp xếp theo mức quan trọng
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Tính phạm vi chương
            start_chapter = max(1, current_chapter - recent_count)
            
            # Lấy ký ức của các chương gần đây
            results = collection.get(
                where={
                    "$and": [
                        {"chapter_number": {"$gte": start_chapter}},
                        {"chapter_number": {"$lt": current_chapter}},
                        {"importance": {"$gte": min_importance}}
                    ]
                },
                limit=100  # Lấy đủ nhiều ký ức trước
            )
            
            memories = []
            if results['ids']:
                for i in range(len(results['ids'])):
                    memories.append({
                        "id": results['ids'][i],
                        "content": results['documents'][i],
                        "metadata": results['metadatas'][i]
                    })
            
            # Sắp xếp theo mức quan trọng và số chương
            memories.sort(
                key=lambda x: (float(x['metadata'].get('importance', 0)), 
                              int(x['metadata'].get('chapter_number', 0))),
                reverse=True
            )
            
            # Trả vềN
            top_memories = memories[:20]
            logger.info(f"📚 Lấy ký ức gần đây: chương{start_chapter}-{current_chapter-1}, tìm thấy{len(top_memories)}")
            return top_memories
            
        except Exception as e:
            logger.error(f"❌ Lấy ký ức gần đây thất bại: {str(e)}")
            return []
    
    async def find_unresolved_foreshadows(
        self,
        user_id: str,
        project_id: str,
        current_chapter: int
    ) -> List[Dict[str, Any]]:
        """
        Tìm các phục bút chưa kết thúc
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            current_chapter: Số chương hiện tại
        
        Returns:
            Danh sách phục bút chưa kết thúc
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Tìm ký ức có trạng thái phục bút là 1 (đã gieo nhưng chưa thu hồi)
            results = collection.get(
                where={
                    "$and": [
                        {"is_foreshadow": 1},
                        {"chapter_number": {"$lt": current_chapter}}
                    ]
                },
                limit=50
            )
            
            foreshadows = []
            if results['ids']:
                for i in range(len(results['ids'])):
                    foreshadows.append({
                        "id": results['ids'][i],
                        "content": results['documents'][i],
                        "metadata": results['metadatas'][i]
                    })
            
            # Sắp xếp theo mức quan trọng
            foreshadows.sort(
                key=lambda x: float(x['metadata'].get('importance', 0)),
                reverse=True
            )
            
            logger.info(f"🎣 Tìm thấy phục bút chưa kết thúc: {len(foreshadows)}")
            return foreshadows
            
        except Exception as e:
            logger.error(f"❌ Tìm phục bút thất bại: {str(e)}")
            return []
    
    async def build_context_for_generation(
        self,
        user_id: str,
        project_id: str,
        current_chapter: int,
        chapter_outline: str,
        character_names: List[str] = None
    ) -> Dict[str, Any]:
        """
        Xây dựng ngữ cảnh thông minh cho việc tạo chương
        
        Đây là tính năng cốt lõi: kết hợp nhiều chiến lược truy xuất để cung cấp cho AI các ký ức liên quan nhất khi tạo nội dung
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            current_chapter: Số chương hiện tại
            chapter_outline: Dàn ý chương này
            character_names: Danh sách tên nhân vật liên quan
        
        Returns:
            Dict chứa đủ loại thông tin ngữ cảnh
        """
        logger.info(f"🧠 Bắt đầu xây dựng{current_chapter}ngữ cảnh thông minh...")
        
        # 1. Lấy ngữ cảnh các chương gần đây(Tính liên tục thời gian)
        recent = await self.get_recent_memories(
            user_id, project_id, current_chapter, 
            recent_count=3, min_importance=0.5
        )
        
        # 2. Tìm kiếm ngữ nghĩa các ký ức liên quan
        relevant = await self.search_memories(
            user_id=user_id,
            project_id=project_id,
            query=chapter_outline,
            limit=10,
            min_importance=0.4
        )
        
        # 3. Tìm các phục bút chưa kết thúc
        foreshadows = await self.find_unresolved_foreshadows(
            user_id, project_id, current_chapter
        )
        
        # 4. Nếu có chỉ định nhân vật,Lấy ký ức liên quan nhân vật
        character_memories = []
        if character_names:
            character_query = " ".join(character_names) + " 角色 状态 关系"
            character_memories = await self.search_memories(
                user_id=user_id,
                project_id=project_id,
                query=character_query,
                memory_types=["character_event", "plot_point"],
                limit=8
            )
        
        # 5. Lấy các điểm cốt truyện quan trọng
        # Lưu ý: điều kiện where của ChromaDB cần xử lý đặc biệt, không thể dùng đồng thời nhiều điều kiện cấp cao nhất
        try:
            plot_points = await self.search_memories(
                user_id=user_id,
                project_id=project_id,
                query="重要 转折 高潮 关键",
                memory_types=["plot_point", "hook"],
                limit=5,
                min_importance=0.7
            )
        except Exception as e:
            logger.error(f"❌ Tìm kiếm ký ức thất bại: {str(e)}")
            # Xử lý hạ cấp: truy vấn riêng từng cái
            plot_points = []
            try:
                plot_points = await self.search_memories(
                    user_id=user_id,
                    project_id=project_id,
                    query="重要 转折 高潮 关键",
                    memory_types=["plot_point", "hook"],
                    limit=5
                )
            except Exception as e2:
                logger.warning(f"⚠️ Truy vấn hạ cấp cũng thất bại: {str(e2)}")
                plot_points = []
        
        context = {
            "recent_context": self._format_memories(recent, "Ký ức các chương gần đây"),
            "relevant_memories": self._format_memories(relevant, "Ký ức liên quan ngữ nghĩa"),
            "character_states": self._format_memories(character_memories, "Ký ức liên quan nhân vật"),
            "foreshadows": self._format_memories(foreshadows[:5], "Phục bút chưa kết thúc"),
            "plot_points": self._format_memories(plot_points, "Điểm cốt truyện quan trọng"),
            "stats": {
                "recent_count": len(recent),
                "relevant_count": len(relevant),
                "character_count": len(character_memories),
                "foreshadow_count": len(foreshadows),
                "plot_point_count": len(plot_points)
            }
        }
        
        logger.info(f"✅ Xây dựng ngữ cảnh hoàn tất: gần đây{len(recent)}, liên quan{len(relevant)}, phục bút{len(foreshadows)}")
        return context
    def _format_memories(self, memories: List[Dict], section_title: str = "ký ức") -> str:
        """
        Định dạng danh sách ký ức thành văn bản
        
        Args:
            memories: Danh sách ký ức
            section_title: Tiêu đề chương
        
        Returns:
            Văn bản sau định dạng
        """
        if not memories:
            return f"[{section_title}]\nTạm thời không có ký ức liên quan\n"
        
        lines = [f"[{section_title}]"]
        for i, mem in enumerate(memories, 1):
            meta = mem.get('metadata', {})
            chapter_num = meta.get('chapter_number', '?')
            mem_type = meta.get('memory_type', 'không rõ')
            importance = float(meta.get('importance', 0.5))
            title = meta.get('title', '')
            content = mem['content']
            
            # Định dạng: [Số thứ tự] Chương X-loại (mức quan trọng) tiêu đề: nội dung
            line = f"{i}. [Chương {chapter_num}-{mem_type}★{importance:.1f}]"
            if title:
                line += f" {title}: {content[:100]}"
            else:
                line += f" {content[:150]}"
            lines.append(line)
        
        return "\n".join(lines) + "\n"
    
    async def delete_foreshadow_memories(
        self,
        user_id: str,
        project_id: str,
        foreshadow_keywords: List[str]
    ) -> int:
        """
        Xóa ký ức phục bút liên quan trong kho vectơ theo từ khóa phục bút
        
        Giải thích: hệ thống ký ức hiện tại chưa bền vững hóa ánh xạ [reference_foreshadow_id](backend/app/services/prompt_service.py:1109) /
        [foreshadow_id](backend/app/services/foreshadow_service.py:230), nên ở đây dùng khớp từ khóa nội dung làm chiến lược dọn dẹp,
        Chỉ xóa ký ức vectơ [memory_type='foreshadow'](backend/app/models/memory.py:23).
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            foreshadow_keywords: Danh sách từ khóa phục bút
        
        Returns:
            Số lượng xóa thực tế
        """
        try:
            keywords = [kw.strip() for kw in foreshadow_keywords if kw and kw.strip()]
            if not keywords:
                return 0

            collection = self.get_collection(user_id, project_id)
            results = collection.get(where={"memory_type": "foreshadow"})

            ids_to_delete = []
            documents = results.get('documents') or []
            metadatas = results.get('metadatas') or []
            result_ids = results.get('ids') or []

            for index, memory_id in enumerate(result_ids):
                document = documents[index] if index < len(documents) else ""
                metadata = metadatas[index] if index < len(metadatas) else {}
                title = str((metadata or {}).get('title', ''))
                haystack = f"{title}\n{document}".lower()

                if any(keyword.lower() in haystack for keyword in keywords):
                    ids_to_delete.append(memory_id)

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"🗑️ Đã xóa {len(ids_to_delete)} ký ức vectơ liên quan phục bút của dự án {project_id[:8]}")

            return len(ids_to_delete)

        except Exception as e:
            logger.error(f"❌ Xóa ký ức vectơ liên quan phục bút thất bại: {str(e)}")
            return 0

    async def delete_chapter_memories(
        self,
        user_id: str,
        project_id: str,
        chapter_id: str
    ) -> bool:
        """
        Xóa mọi ký ức của chương chỉ định
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            chapter_id: chươngID
        
        Returns:
            Đã xóa thành công hay chưa
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Tìm mọi ký ức của chương này
            results = collection.get(
                where={"chapter_id": chapter_id}
            )
            
            if results['ids']:
                # Xóa các ký ức này
                collection.delete(ids=results['ids'])
                logger.info(f"🗑️ Đã xóa {len(results['ids'])} ký ức của chương {chapter_id[:8]}")
                return True
            else:
                logger.info(f"ℹ️ chương{chapter_id[:8]}Không có ký ức nào cần xóa")
                return True
                
        except Exception as e:
            logger.error(f"❌ Xóa ký ức chương thất bại: {str(e)}")
            return False
    
    async def delete_project_memories(
        self,
        user_id: str,
        project_id: str
    ) -> bool:
        """
        Xóa mọi ký ức của dự án chỉ định(bao gồm cơ sở dữ liệu vectơ)
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
        
        Returns:
            Đã xóa thành công hay chưa
        """
        try:
            # tạocollectiontên
            user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
            project_hash = hashlib.sha256(project_id.encode()).hexdigest()[:8]
            collection_name = f"u_{user_hash}_p_{project_hash}"
            
            # Xóa toàn bộcollection(Việc này sẽ dọn sạch mọi dữ liệu vectơ)
            try:
                self.client.delete_collection(name=collection_name)
                logger.info(f"🗑️ Đã xóa dự án{project_id[:8]}cơ sở dữ liệu vectơcollection: {collection_name}")
                return True
            except Exception as e:
                # nếucollectionkhông tồn tại,cũng tính là thành công
                if "does not exist" in str(e).lower():
                    logger.info(f"ℹ️ collection của dự án {project_id[:8]} không tồn tại, không cần xóa")
                    return True
                else:
                    raise
                
        except Exception as e:
            logger.error(f"❌ Xóa ký ức dự án thất bại: {str(e)}")
            return False
    
    async def update_memory(
        self,
        user_id: str,
        project_id: str,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Cập nhật nội dung hoặc siêu dữ liệu của ký ức
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
            memory_id: ký ứcID
            content: Nội dung mới(tùy chọn)
            metadata: Siêu dữ liệu mới(tùy chọn)
        
        Returns:
            Đã cập nhật thành công hay chưa
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            update_data = {}
            
            if content:
                # tạo lạiembedding
                embedding = self.embedding_model.encode(content).tolist()
                update_data['embeddings'] = [embedding]
                update_data['documents'] = [content]
            
            if metadata:
                # Chuẩn bị siêu dữ liệu mới
                chroma_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, (list, dict)):
                        chroma_metadata[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        chroma_metadata[key] = value
                update_data['metadatas'] = [chroma_metadata]
            
            if update_data:
                collection.update(
                    ids=[memory_id],
                    **update_data
                )
                logger.info(f"✅ Ký ức đã được cập nhật: {memory_id[:8]}...")
                return True
            else:
                logger.warning("⚠️ Không cung cấp nội dung cập nhật")
                return False
                
        except Exception as e:
            logger.error(f"❌ Cập nhật ký ức thất bại: {str(e)}")
            return False
    
    async def get_memory_stats(
        self,
        user_id: str,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Lấy thông tin thống kê ký ức
        
        Args:
            user_id: người dùngID
            project_id: dự ánID
        
        Returns:
            Dict thông tin thống kê
        """
        try:
            collection = self.get_collection(user_id, project_id)
            
            # Lấy mọi ký ức
            all_memories = collection.get()
            
            if not all_memories['ids']:
                return {
                    "total_count": 0,
                    "by_type": {},
                    "by_chapter": {},
                    "foreshadow_count": 0
                }
            
            # Thống kê số lượng từng loại
            type_counts = {}
            chapter_counts = {}
            foreshadow_count = 0
            
            for i, meta in enumerate(all_memories['metadatas']):
                mem_type = meta.get('memory_type', 'unknown')
                chapter_num = meta.get('chapter_number', 0)
                is_foreshadow = meta.get('is_foreshadow', 0)
                
                type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
                chapter_counts[str(chapter_num)] = chapter_counts.get(str(chapter_num), 0) + 1
                
                if is_foreshadow == 1:
                    foreshadow_count += 1
            
            stats = {
                "total_count": len(all_memories['ids']),
                "by_type": type_counts,
                "by_chapter": chapter_counts,
                "foreshadow_count": foreshadow_count,
                "foreshadow_resolved": sum(1 for m in all_memories['metadatas'] if m.get('is_foreshadow') == 2)
            }
            
            logger.info(f"📊 Thống kê ký ức: Tổng cộng{stats['total_count']}, phục bút{foreshadow_count}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Lấy thông tin thống kê thất bại: {str(e)}")
            return {"error": str(e)}


# Tạo thể hiện toàn cục
memory_service = MemoryService()
