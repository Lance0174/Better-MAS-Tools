/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WikiCalendarAllOut } from '../models/WikiCalendarAllOut';
import type { WikiCalendarOut } from '../models/WikiCalendarOut';
import type { WikiEntryOut } from '../models/WikiEntryOut';
import type { WikiSearchOut } from '../models/WikiSearchOut';
import type { WikiStatusOut } from '../models/WikiStatusOut';
import type { WikiSyncIn } from '../models/WikiSyncIn';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class WikiService {
    /**
     * Get Status
     * @returns WikiStatusOut Successful Response
     * @throws ApiError
     */
    public static getWikiStatus(): CancelablePromise<WikiStatusOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/wiki/status',
        });
    }
    /**
     * Sync
     * @param requestBody
     * @returns WikiStatusOut Successful Response
     * @throws ApiError
     */
    public static syncWikiData(
        requestBody?: (WikiSyncIn | null),
    ): CancelablePromise<WikiStatusOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/wiki/sync',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Search
     * @param q 关键词：名称、昵称或简称
     * @param limit
     * @returns WikiSearchOut Successful Response
     * @throws ApiError
     */
    public static searchWikiEntries(
        q: string = '',
        limit: number = 20,
    ): CancelablePromise<WikiSearchOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/wiki/search',
            query: {
                'q': q,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Entry
     * @param kind
     * @param id
     * @returns WikiEntryOut Successful Response
     * @throws ApiError
     */
    public static getWikiEntry(
        kind: 'character' | 'weapon' | 'equipSuit' | 'dungeon' | 'enemy',
        id: string,
    ): CancelablePromise<WikiEntryOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/wiki/entry',
            query: {
                'kind': kind,
                'id': id,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Calendar
     * @param game
     * @returns WikiCalendarOut Successful Response
     * @throws ApiError
     */
    public static getWikiCalendar(
        game: 'endfield' | 'arknights' | 'genshin' | 'starrail' | 'zenless' | 'wutheringwaves' | 'nte' | 'stellasora',
    ): CancelablePromise<WikiCalendarOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/wiki/calendar',
            query: {
                'game': game,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Calendar All
     * @returns WikiCalendarAllOut Successful Response
     * @throws ApiError
     */
    public static getWikiCalendarAll(): CancelablePromise<WikiCalendarAllOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/wiki/calendar-all',
        });
    }
}
