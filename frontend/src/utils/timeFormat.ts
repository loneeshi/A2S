/**
 * Time Format - 时间格式化工具
 */

export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    const mins = minutes % 60;
    const secs = seconds % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  } else if (minutes > 0) {
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  } else {
    return `${seconds}.${(ms % 1000).toString().padStart(3, '0')}s`;
  }
}

export function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
}
