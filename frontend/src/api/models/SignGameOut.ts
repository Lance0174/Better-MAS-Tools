/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SignDetailInfo } from './SignDetailInfo';
export type SignGameOut = {
    account?: string;
    game?: string;
    status?: string;
    reward?: string;
    reason?: string;
    /**
     * 实际执行时间，ISO 8601 北京时间
     */
    signedAt?: string;
    /**
     * 分项签到结果；空列表表示旧版合并结果，共享社区签到只出现一次
     */
    details?: Array<SignDetailInfo>;
};

