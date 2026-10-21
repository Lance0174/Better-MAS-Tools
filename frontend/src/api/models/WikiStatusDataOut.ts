/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WikiCountsOut } from './WikiCountsOut';
/**
 * 资料库状态；ready=false 时 counts 全为 0，problems 为空。
 */
export type WikiStatusDataOut = {
    ready?: boolean;
    version?: string;
    /**
     * 上次同步时间，ISO 8601 北京时间
     */
    updatedAt?: string;
    /**
     * 本机索引的布局版本，与程序不一致时需要重建
     */
    schema?: number;
    counts?: WikiCountsOut;
    /**
     * 数据体检发现的问题
     */
    problems?: Array<string>;
    message?: string;
};

