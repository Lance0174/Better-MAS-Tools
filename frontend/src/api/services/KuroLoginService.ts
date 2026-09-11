/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { KuroSmsAutomaticOut } from '../models/KuroSmsAutomaticOut';
import type { KuroSmsCreateIn } from '../models/KuroSmsCreateIn';
import type { KuroSmsCreateOut } from '../models/KuroSmsCreateOut';
import type { KuroSmsLoginIn } from '../models/KuroSmsLoginIn';
import type { KuroSmsSendIn } from '../models/KuroSmsSendIn';
import type { KuroSmsSessionIn } from '../models/KuroSmsSessionIn';
import type { OutBase } from '../models/OutBase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class KuroLoginService {
    /**
     * Automatic Sms
     * @param requestBody
     * @returns KuroSmsAutomaticOut Successful Response
     * @throws ApiError
     */
    public static automaticKuroSms(
        requestBody: KuroSmsSessionIn,
    ): CancelablePromise<KuroSmsAutomaticOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/kuro/sms/automatic',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Sms
     * @param requestBody
     * @returns KuroSmsCreateOut Successful Response
     * @throws ApiError
     */
    public static createKuroSms(
        requestBody: KuroSmsCreateIn,
    ): CancelablePromise<KuroSmsCreateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/kuro/sms/create',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Send Sms
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static sendKuroSms(
        requestBody: KuroSmsSendIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/kuro/sms/send',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Login Sms
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static loginKuroSms(
        requestBody: KuroSmsLoginIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/kuro/sms/login',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Cancel Sms
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static cancelKuroSms(
        requestBody: KuroSmsSessionIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/kuro/sms/cancel',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
