/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WikiCalendarRowOut } from './WikiCalendarRowOut';
/**
 * 单个游戏的日历；某个游戏取不到数据时只影响它自己。
 */
export type WikiCalendarGameOut = {
    game: 'endfield' | 'arknights' | 'genshin' | 'starrail' | 'zenless' | 'wutheringwaves' | 'nte' | 'stellasora';
    name?: string;
    /**
     * 数据来源：sra / cache（TTL 内缓存）/ stale-cache（回落到上次成功结果） / local（本机解包索引）/ none（无数据）
     */
    source?: string;
    /**
     * SRA 上的版本号；没有时为空
     */
    version?: string;
    /**
     * 当前版本名，前端可作卡片标题
     */
    versionName?: string;
    /**
     * 当前版本主视觉；缺失是常态，前端需自备占位
     */
    cover?: string;
    activities?: Array<WikiCalendarRowOut>;
    message?: string;
};

