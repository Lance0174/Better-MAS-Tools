/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * 米游社 Cookie 换 authkey 的读取入参；cookie 只在本次请求内使用。
 */
export type GachaCookieFetchIn = {
    game: 'genshin' | 'starrail' | 'zzz';
    /**
     * 账号组 ID；cookie 留空时从这里取已绑定的米游社凭据
     */
    accountId?: string;
    /**
     * 游戏 UID（纯数字）
     */
    playerUid: string;
    /**
     * 米游社 Cookie；留空则用账号组里保存的那份
     */
    cookie?: string;
    /**
     * 区域，如 cn_gf01/prod_gf_cn；留空按 UID 推断
     */
    region?: string;
    timezone?: number;
    maxPages?: number;
};

