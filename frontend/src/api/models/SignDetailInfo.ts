/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 一次游戏签到或账号共享的社区签到结果。
 */
export type SignDetailInfo = {
    /**
     * 签到任务类型
     */
    kind: 'game' | 'community';
    status?: string;
    reward?: string;
    reason?: string;
};

