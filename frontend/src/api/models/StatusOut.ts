/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SignAccountOut } from './SignAccountOut';
export type StatusOut = {
    /**
     * 状态码
     */
    code?: number;
    /**
     * 操作状态
     */
    status?: string;
    /**
     * 操作消息
     */
    message?: string;
    running?: boolean;
    activityRunning?: boolean;
    revision?: number;
    /**
     * 服务端北京时间日期
     */
    today?: string;
    results?: Record<string, Array<SignAccountOut>>;
};

