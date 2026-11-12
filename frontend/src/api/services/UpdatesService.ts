/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UpdateCheckOut } from '../models/UpdateCheckOut';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class UpdatesService {
    /**
     * Check
     * @param platform
     * @param channel
     * @returns UpdateCheckOut Successful Response
     * @throws ApiError
     */
    public static checkUpdates(
        platform: 'windows' | 'android',
        channel: 'stable' | 'beta' = 'stable',
    ): CancelablePromise<UpdateCheckOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/updates/check',
            query: {
                'platform': platform,
                'channel': channel,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
