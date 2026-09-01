import { useEffect } from 'react';
import { initTelegram } from './telegram';

export function useTelegramInit() {
  useEffect(() => {
    initTelegram();
  }, []);
}
