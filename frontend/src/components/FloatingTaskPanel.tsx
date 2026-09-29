import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, List, Button, Space, Badge, Tag, Progress, Popconfirm, Empty, theme, Tooltip, message } from 'antd';
import {
  ClockCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
  UpOutlined,
  DownOutlined,
  ClearOutlined,
} from '@ant-design/icons';
import { getProjectTasks, getTaskStatus, cancelTask, cancelBatchTask, deleteTask, clearProjectTasks, type TaskStatus } from '../services/backgroundTaskService';
import { eventBus, EventNames } from '../store/eventBus';

interface FloatingTaskPanelProps {
  projectId: string;
  autoRefreshInterval?: number; // Khoảng thời gian tự refresh (ms), mặc định 3000
  rightOffset?: number;
}

/**
 * Component hộp task nổi
 * Hiển thị ở góc dưới bên phải trang, hỗ trợ thu gọn/mở rộng
 */
export const FloatingTaskPanel: React.FC<FloatingTaskPanelProps> = ({
  projectId,
  autoRefreshInterval = 3000,
  rightOffset = 23,
}) => {
  const [taskList, setTaskList] = useState<TaskStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(true); // Mặc định thu gọn
  const userCollapsedRef = useRef(false); // Cờ người dùng thu gọn thủ công
  const taskStatusRef = useRef<Map<string, TaskStatus['status']>>(new Map());
  const watchedTaskIdsRef = useRef<Set<string>>(new Set());
  const loadRequestIdRef = useRef(0);
  const { token } = theme.useToken();

  // Tải danh sách task
  const loadTasks = useCallback(async () => {
    if (!projectId) return;
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    try {
      const result = await getProjectTasks(projectId);
      if (requestId !== loadRequestIdRef.current) return;
      const nextTasks = result.items || [];
      const visibleTaskIds = new Set(nextTasks.map(task => task.id));
      // Danh sách có giới hạn số lượng. Với task agent vừa tạo nhưng chưa xuất hiện trong danh sách thì truy vấn theo ID,
      // tránh bị nhiều task đang hoạt động đẩy ra khiến không nhận biết được trạng thái hoàn tất.
      const missingWatchedTasks = await Promise.all(
        [...watchedTaskIdsRef.current]
          .filter(taskId => !visibleTaskIds.has(taskId))
          .map(taskId => getTaskStatus(taskId).catch(() => null)),
      );
      if (requestId !== loadRequestIdRef.current) return;

      const observedTasks = [
        ...nextTasks,
        ...missingWatchedTasks.filter((task): task is TaskStatus => task !== null),
      ];
      observedTasks.forEach(task => {
        const previousStatus = taskStatusRef.current.get(task.id);
        const wasActive = previousStatus === 'running' || previousStatus === 'pending';
        const isSettled = task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled';
        const isWatchedTask = watchedTaskIdsRef.current.has(task.id);
        if (isSettled && (wasActive || isWatchedTask)) {
          eventBus.emit(EventNames.BACKGROUND_TASK_SETTLED, {
            projectId: task.project_id,
            taskId: task.id,
            resources: task.affected_resources || [],
            task,
          });
          watchedTaskIdsRef.current.delete(task.id);
        }
      });
      taskStatusRef.current = new Map(observedTasks.map(task => [task.id, task.status]));
      setTaskList(nextTasks);
    } catch (error) {
      console.error('Tải danh sách task thất bại:', error);
    } finally {
      if (requestId === loadRequestIdRef.current) setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    taskStatusRef.current.clear();
    watchedTaskIdsRef.current.clear();
    loadRequestIdRef.current += 1;
  }, [projectId]);

  // Tải ban đầu
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Lắng nghe sự kiện tạo task nền, refresh ngay danh sách và mở cửa sổ nổi
  useEffect(() => {
    const handleTaskCreated = (payload?: unknown) => {
      if (payload && typeof payload === 'object') {
        const eventPayload = payload as { projectId?: unknown; taskId?: unknown };
        if (typeof eventPayload.projectId === 'string' && eventPayload.projectId !== projectId) return;
        const taskId = eventPayload.taskId;
        if (typeof taskId === 'string') watchedTaskIdsRef.current.add(taskId);
      }
      void loadTasks();
      // Tự mở rộng khi tạo task mới (đặt lại cờ người dùng thu gọn thủ công)
      userCollapsedRef.current = false;
      setCollapsed(false);
    };
    eventBus.on(EventNames.BACKGROUND_TASK_CREATED, handleTaskCreated);
    // Tương thích thông báo tạo task trong trang chưa được migrate.
    eventBus.on('background-task-created', handleTaskCreated);
    return () => {
      eventBus.off(EventNames.BACKGROUND_TASK_CREATED, handleTaskCreated);
      eventBus.off('background-task-created', handleTaskCreated);
    };
  }, [loadTasks, projectId]);

  // Tự mở rộng khi có task đang hoạt động (chỉ khi người dùng không thu gọn thủ công)
  useEffect(() => {
    const hasActiveTasks = taskList.some(
      (t) => t.status === 'running' || t.status === 'pending'
    );
    if (hasActiveTasks && !userCollapsedRef.current) {
      setCollapsed(false);
    }
  }, [taskList]);

  // Task đang hoạt động refresh tần suất cao; khi rảnh giữ refresh tần suất thấp để phát hiện task tạo từ tab khác hoặc bên ngoài.
  useEffect(() => {
    const hasActiveTasks = taskList.some(
      (t) => t.status === 'running' || t.status === 'pending'
    );
    
    const interval = hasActiveTasks ? autoRefreshInterval : Math.max(autoRefreshInterval * 5, 15000);
    const timer = setInterval(loadTasks, interval);
    return () => clearInterval(timer);
  }, [taskList, autoRefreshInterval, loadTasks]);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void loadTasks();
    };
    window.addEventListener('focus', refreshWhenVisible);
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      window.removeEventListener('focus', refreshWhenVisible);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, [loadTasks]);

  // Hủy task
  const handleCancelTask = async (task: TaskStatus) => {
    try {
      if (task.task_type === 'chapter_batch') {
        await cancelBatchTask(task.id);
      } else {
        await cancelTask(task.id);
      }
      loadTasks();
    } catch (error) {
      console.error('Hủy task thất bại:', error);
    }
  };

  // Xóa bản ghi task
  const handleDeleteTask = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      loadTasks();
    } catch (error) {
      console.error('Xóa bản ghi task thất bại:', error);
    }
  };

  // Dọn bằng một nhấn các bản ghi task đã kết thúc
  const handleClearTasks = async () => {
    try {
      const result = await clearProjectTasks(projectId);
      message.success(`Đã dọn ${result.deleted_count} bản ghi task`);
      loadTasks();
    } catch (error) {
      console.error('Dọn bản ghi task thất bại:', error);
      message.error('Dọn bản ghi task thất bại');
    }
  };

  // Lấy nhãn trạng thái task
  const getTaskStatusTag = (status: TaskStatus['status']) => {
    switch (status) {
      case 'pending':
        return <Tag icon={<ClockCircleOutlined />} color="default">Đang chờ</Tag>;
      case 'running':
        return <Tag icon={<LoadingOutlined />} color="processing">Đang chạy</Tag>;
      case 'completed':
        return <Tag icon={<CheckCircleOutlined />} color="success">Đã hoàn tất</Tag>;
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">Thất bại</Tag>;
      case 'cancelled':
        return <Tag icon={<CloseCircleOutlined />} color="default">Đã hủy</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  // Lấy nhãn loại task
  const getTaskTypeLabel = (taskType: string) => {
    switch (taskType) {
      case 'outline_new':
        return 'Tạo đề cương';
      case 'outline_continue':
        return 'Viết tiếp đề cương';
      case 'outline_expand':
        return 'Mở rộng đề cương';
      case 'outline_batch_expand':
        return 'Mở rộng đề cương hàng loạt';
      case 'chapter_generate':
        return 'Tạo chương';
      case 'chapter_batch':
        return 'Tạo chương hàng loạt';
      case 'wizard':
        return 'Tạo bằng wizard';
      case 'chapter_analysis':
        return 'Phân tích chương';
      case 'chapter_regenerate':
        return 'Viết lại chương';
      case 'chapter_partial_regenerate':
        return 'Viết lại cục bộ';
      case 'character_generate':
        return 'Tạo nhân vật';
      case 'organization_generate':
        return 'Tạo tổ chức';
      case 'career_generate':
        return 'Tạo nghề nghiệp';
      default:
        return taskType;
    }
  };

  const activeTasks = taskList.filter((t) => t.status === 'running' || t.status === 'pending');
  const hasActiveTasks = activeTasks.length > 0;

  // Không hiển thị cửa sổ nổi khi không có task
  if (taskList.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 10,
        right: rightOffset,
        width: collapsed ? 260 : 400,
        maxHeight: collapsed ? 60 : 500,
        zIndex: 1000,
        boxShadow: token.boxShadowSecondary,
        borderRadius: token.borderRadiusLG,
        overflow: 'hidden',
        transition: 'all 0.3s ease',
      }}
    >
      <Card
        size="small"
        title={
          <Space>
            <ClockCircleOutlined />
            <span>Task nền</span>
            {hasActiveTasks && <Badge count={activeTasks.length} />}
          </Space>
        }
        extra={
          <Space>
            <Tooltip title="Làm mới">
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                onClick={loadTasks}
                loading={loading}
              />
            </Tooltip>
            {taskList.some(t => t.can_delete && (
              t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled'
            )) && (
              <Popconfirm
                title="Xác nhận dọn tất cả bản ghi task đã kết thúc?"
                onConfirm={handleClearTasks}
                okText="Xác nhận"
                cancelText="Hủy"
              >
                <Tooltip title="Dọn task đã kết thúc">
                  <Button
                    type="text"
                    size="small"
                    icon={<ClearOutlined />}
                  />
                </Tooltip>
              </Popconfirm>
            )}
            <Button
              type="text"
              size="small"
              icon={collapsed ? <UpOutlined /> : <DownOutlined />}
              onClick={() => {
                const newCollapsed = !collapsed;
                setCollapsed(newCollapsed);
                // Ghi lại người dùng thu gọn thủ công, tránh tự mở rộng ghi đè
                userCollapsedRef.current = newCollapsed;
              }}
            />
          </Space>
        }
        bodyStyle={{
          padding: collapsed ? 0 : 12,
          maxHeight: collapsed ? 0 : 400,
          overflowY: 'auto',
          transition: 'all 0.3s ease',
        }}
      >
        {!collapsed && (
          <>
            {taskList.length === 0 ? (
              <Empty description="Chưa có task" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                size="small"
                dataSource={taskList}
                renderItem={(task: TaskStatus) => (
                  <List.Item
                    key={task.id}
                    style={{
                      padding: '8px 0',
                      borderBottom: `1px solid ${token.colorBorderSecondary}`,
                    }}
                  >
                    <div style={{ width: '100%' }}>
                      <div style={{ marginBottom: 4 }}>
                        <Space size={4} wrap>
                          {getTaskStatusTag(task.status)}
                          <Tag color="blue">{getTaskTypeLabel(task.task_type)}</Tag>
                        </Space>
                      </div>

                      {task.status_message && (
                        <div
                          style={{
                            fontSize: 12,
                            color: token.colorTextSecondary,
                            marginBottom: 4,
                          }}
                        >
                          {task.status_message}
                        </div>
                      )}

                      {(task.status === 'running' || task.status === 'pending') && (
                        <Progress
                          percent={task.progress}
                          size="small"
                          status={task.status === 'running' ? 'active' : 'normal'}
                          style={{ marginBottom: 4 }}
                        />
                      )}

                      {task.error_message && (
                        <div
                          style={{
                            fontSize: 12,
                            color: token.colorError,
                            marginBottom: 4,
                          }}
                        >
                          Lỗi: {task.error_message}
                        </div>
                      )}

                      <div style={{ marginTop: 8 }}>
                        <Space size={4}>
                          {task.can_cancel && (task.status === 'running' || task.status === 'pending') && (
                            <Popconfirm
                              title="Xác nhận hủy task?"
                              onConfirm={() => handleCancelTask(task)}
                              okText="Xác nhận"
                              cancelText="Hủy"
                            >
                              <Button size="small" danger>
                                Hủy
                              </Button>
                            </Popconfirm>
                          )}
                          {task.can_delete && (task.status === 'completed' ||
                            task.status === 'failed' ||
                            task.status === 'cancelled') && (
                              <Popconfirm
                                title="Xác nhận xóa bản ghi task?"
                                onConfirm={() => handleDeleteTask(task.id)}
                                okText="Xác nhận"
                                cancelText="Hủy"
                              >
                                <Button size="small" icon={<DeleteOutlined />}>
                                  Xóa
                                </Button>
                              </Popconfirm>
                            )}
                        </Space>
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </>
        )}
      </Card>
    </div>
  );
};

export default FloatingTaskPanel;
