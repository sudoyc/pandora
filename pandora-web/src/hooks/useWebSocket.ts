import { useEffect, useState } from 'react';

export interface DownloadProgress {
  type: 'download_progress';
  gid: string;
  progress: number;
  status: string;
}

export const useWebSocket = () => {
  const [messages, setMessages] = useState<DownloadProgress[]>([]);

  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:7860/ws');
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'download_progress') {
          setMessages(prev => {
            // Update existing or add new
            const index = prev.findIndex(m => m.gid === data.gid);
            if (index !== -1) {
              const updated = [...prev];
              updated[index] = data;
              return updated;
            }
            return [...prev, data];
          });
        }
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.close();
  }, []);

  return messages;
};
