import type { BowlWashStatus, MillStatus } from './types';

export const millStatusLabel: Record<MillStatus, string> = {
  grinding: '研磨中',
  idle: '待机',
  wash: '清洗',
};

export const bowlWashStatusLabel: Record<BowlWashStatus, string> = {
  open: '待洗机',
  washing: '洗机中',
  done: '已完成',
  void: '已作废',
};
