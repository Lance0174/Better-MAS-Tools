/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CloudSyncIn } from '../models/CloudSyncIn';
import type { CloudSyncOut } from '../models/CloudSyncOut';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CloudService {
    /**
     * Cloud Sync
     * @param requestBody
     * @returns CloudSyncOut Successful Response
     * @throws ApiError
     */
    public static cloudSync(
        requestBody: CloudSyncIn,
    ): CancelablePromise<CloudSyncOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/cloud/sync',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
