/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CloudSyncResult } from './CloudSyncResult';
export type CloudSyncOut = {
    /**
     * 状态码
     */
    code?: number;
    /**
     * 操作状态
     */
    status?: string;
    message?: string;
    data?: Array<CloudSyncResult>;
};

