/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CloudAccountIn } from './CloudAccountIn';
/**
 * 云端签到同步请求：本地把账号 token 与执行开关交给云端。
 */
export type CloudSyncIn = {
    accounts?: Array<CloudAccountIn>;
    miyoushe_bbs?: boolean;
};

