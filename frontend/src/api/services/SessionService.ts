/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SessionLoginIn } from '../models/SessionLoginIn';
import type { SessionOut } from '../models/SessionOut';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SessionService {
    /**
     * Session
     * @returns SessionOut Successful Response
     * @throws ApiError
     */
    public static getSession(): CancelablePromise<SessionOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/session',
        });
    }
    /**
     * Login Session
     * @param requestBody
     * @returns SessionOut Successful Response
     * @throws ApiError
     */
    public static loginSession(
        requestBody: SessionLoginIn,
    ): CancelablePromise<SessionOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/session',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
