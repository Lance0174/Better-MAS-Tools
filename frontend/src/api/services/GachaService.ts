/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GachaCookieFetchIn } from '../models/GachaCookieFetchIn';
import type { GachaExportOut } from '../models/GachaExportOut';
import type { GachaFetchIn } from '../models/GachaFetchIn';
import type { GachaHeyboxIn } from '../models/GachaHeyboxIn';
import type { GachaHeyboxOut } from '../models/GachaHeyboxOut';
import type { GachaImportIn } from '../models/GachaImportIn';
import type { GachaRecordsOut } from '../models/GachaRecordsOut';
import type { GachaUpdateOut } from '../models/GachaUpdateOut';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class GachaService {
    /**
     * List Records
     * @param game
     * @param playerUid
     * @param pool
     * @param page
     * @param pageSize
     * @returns GachaRecordsOut Successful Response
     * @throws ApiError
     */
    public static listGachaRecords(
        game: 'genshin' | 'starrail' | 'zzz' | 'wuthering' | 'arknights' | 'endfield',
        playerUid: string = '',
        pool: string = '',
        page: number = 1,
        pageSize: number = 50,
    ): CancelablePromise<GachaRecordsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/gacha',
            query: {
                'game': game,
                'playerUid': playerUid,
                'pool': pool,
                'page': page,
                'pageSize': pageSize,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Fetch Records
     * @param requestBody
     * @returns GachaUpdateOut Successful Response
     * @throws ApiError
     */
    public static fetchGachaRecords(
        requestBody: GachaFetchIn,
    ): CancelablePromise<GachaUpdateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/gacha/fetch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * @deprecated
     * Fetch Records By Cookie
     * 旧米游社 Cookie 入口暂不开放，返回 400；明日方舟使用 /fetch 的森空岛账号授权。
     * @param requestBody
     * @returns GachaUpdateOut Successful Response
     * @throws ApiError
     */
    public static fetchGachaRecordsByCookie(
        requestBody: GachaCookieFetchIn,
    ): CancelablePromise<GachaUpdateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/gacha/fetch-cookie',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Import Records
     * @param requestBody
     * @returns GachaUpdateOut Successful Response
     * @throws ApiError
     */
    public static importGachaRecords(
        requestBody: GachaImportIn,
    ): CancelablePromise<GachaUpdateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/gacha/import',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Import Heybox
     * @param requestBody
     * @returns GachaHeyboxOut Successful Response
     * @throws ApiError
     */
    public static importGachaHeybox(
        requestBody: GachaHeyboxIn,
    ): CancelablePromise<GachaHeyboxOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/gacha/heybox',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Revoke Heybox
     * @param playerUid
     * @param game
     * @returns GachaUpdateOut Successful Response
     * @throws ApiError
     */
    public static revokeGachaHeybox(
        playerUid: string,
        game: string = 'endfield',
    ): CancelablePromise<GachaUpdateOut> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/gacha/heybox',
            query: {
                'game': game,
                'playerUid': playerUid,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Export Records
     * @param game
     * @param playerUid
     * @param fileFormat
     * @returns GachaExportOut Successful Response
     * @throws ApiError
     */
    public static exportGachaRecords(
        game: 'genshin' | 'starrail' | 'zzz' | 'wuthering' | 'arknights' | 'endfield',
        playerUid: string = '',
        fileFormat: 'bmasc' | 'uigf' = 'bmasc',
    ): CancelablePromise<GachaExportOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/gacha/export',
            query: {
                'game': game,
                'playerUid': playerUid,
                'fileFormat': fileFormat,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
