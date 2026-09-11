/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MasQueueOut } from './MasQueueOut';
import type { MasTaskOut } from './MasTaskOut';
export type MasSnapshotOut = {
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
    baseUrl: string;
    queues?: Array<MasQueueOut>;
    tasks?: Array<MasTaskOut>;
};

