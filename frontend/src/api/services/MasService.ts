/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MasSnapshotOut } from '../models/MasSnapshotOut';
import type { MasStartIn } from '../models/MasStartIn';
import type { MasStartOut } from '../models/MasStartOut';
import type { MasStopIn } from '../models/MasStopIn';
import type { OutBase } from '../models/OutBase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MasService {
    /**
     * Snapshot
     * @returns MasSnapshotOut Successful Response
     * @throws ApiError
     */
    public static getMasSnapshot(): CancelablePromise<MasSnapshotOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/mas/snapshot',
        });
    }
    /**
     * Start
     * @param requestBody
     * @returns MasStartOut Successful Response
     * @throws ApiError
     */
    public static startMasTask(
        requestBody: MasStartIn,
    ): CancelablePromise<MasStartOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/mas/start',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Stop
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static stopMasTask(
        requestBody: MasStopIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/mas/stop',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
