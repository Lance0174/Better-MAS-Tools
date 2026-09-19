/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 执行层回传的指令结果；data 只允许 JSON 兼容值。
 */
export type RelayResultIn = {
    nodeId: string;
    commandId: string;
    ok: boolean;
    data?: Record<string, any>;
    error?: string;
    finishedAt?: string;
};

