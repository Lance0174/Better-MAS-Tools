/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SettingsData } from './SettingsData';
export type SettingsOut = {
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
    data: SettingsData;
    yunmaConfigured?: boolean;
    /**
     * 是否能连接后端主机的 MAS 与代理；纯 Workers 为 false
     */
    localConnections?: boolean;
};

