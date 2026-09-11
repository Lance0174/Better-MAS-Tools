/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GachaExportOut } from '../models/GachaExportOut';
import type { GachaFetchIn } from '../models/GachaFetchIn';
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
