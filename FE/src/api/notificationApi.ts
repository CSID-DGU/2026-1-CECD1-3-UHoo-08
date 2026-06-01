import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  isRead: boolean;
  actionUrl: string | null;
  createdAt: string;
}

export interface NotificationList {
  unreadCount: number;
  notifications: NotificationItem[];
  total: number;
}

export const getNotifications = (page = 1, size = 20) =>
  api.get<ApiResponse<NotificationList>>(`/notifications?page=${page}&size=${size}`);

export const getUnreadCount = async (): Promise<number> => {
  const res = await getNotifications(1, 1);
  return res.data.unreadCount;
};

export const markAllAsRead = () =>
  api.patch<ApiResponse<{ updatedCount: number }>>("/notifications/read-all");

export const markAsRead = (notificationId: string) =>
  api.patch<ApiResponse<{ notificationId: string; isRead: boolean }>>(
    `/notifications/${notificationId}`,
  );
