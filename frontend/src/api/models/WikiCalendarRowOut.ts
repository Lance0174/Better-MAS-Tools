/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WikiCalendarRowOut = {
    game: 'endfield' | 'arknights' | 'genshin' | 'starrail' | 'zenless' | 'wutheringwaves' | 'nte' | 'stellasora' | 'infinitynikki';
    kind: 'activity' | 'gacha';
    title: string;
    subtitle?: string;
    /**
     * ISO 8601 北京时间；常驻活动为空
     */
    startsAt?: string;
    endsAt?: string;
    banner?: string;
    /**
     * 进行中 / 即将开始 / 已结束 / 常驻
     */
    status?: string;
};

