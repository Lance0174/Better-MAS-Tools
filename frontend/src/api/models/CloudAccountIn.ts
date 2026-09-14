/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 本地账号上传到云端执行；token 只用于本次请求，云端不持久化。
 */
export type CloudAccountIn = {
    uid: string;
    name?: string;
    tokens?: Record<string, string>;
    enabled?: boolean;
};

