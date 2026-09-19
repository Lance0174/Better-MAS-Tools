/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 控制端下发的转发指令；类型受白名单限制，payload 形状由执行层校验。
 */
export type RelayCommandIn = {
    type: 'mas.snapshot' | 'mas.start' | 'mas.stop' | 'sign.run';
    payload?: Record<string, any>;
};

