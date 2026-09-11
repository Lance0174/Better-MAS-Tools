/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GachaPoolOut } from './GachaPoolOut';
import type { GachaRecord } from './GachaRecord';
export type GachaRecordsOut = {
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
    data?: Array<GachaRecord>;
    total?: number;
    players?: Array<string>;
    pools?: Array<GachaPoolOut>;
};

