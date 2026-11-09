/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 小黑盒补录结果：added 是新增、replaced 是被替换的旧补录行。
 */
export type GachaHeyboxOut = {
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
    added?: number;
    replaced?: number;
    skipped?: Array<string>;
    warnings?: Array<string>;
};

