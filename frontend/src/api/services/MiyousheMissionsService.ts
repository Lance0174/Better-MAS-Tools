/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MiyousheVerificationIn } from '../models/MiyousheVerificationIn';
import type { MiyousheVerificationsOut } from '../models/MiyousheVerificationsOut';
import type { OutBase } from '../models/OutBase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MiyousheMissionsService {
    /**
     * List Verifications
     * @returns MiyousheVerificationsOut Successful Response
     * @throws ApiError
     */
    public static listMiyousheVerifications(): CancelablePromise<MiyousheVerificationsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/miyoushe/verification',
        });
    }
    /**
     * Submit
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static submitMiyousheVerification(
        requestBody: MiyousheVerificationIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/miyoushe/verification/submit',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
