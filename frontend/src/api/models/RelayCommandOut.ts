/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 转发层下发给执行层的指令信封；version 供通道升级使用。
 */
export type RelayCommandOut = {
    id: string;
    type: string;
    payload?: Record<string, any>;
    createdAt?: string;
    expireAt?: string;
    version?: number;
};

