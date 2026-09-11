/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClientLogIn } from '../models/ClientLogIn';
import type { LogExportOut } from '../models/LogExportOut';
import type { LogsOut } from '../models/LogsOut';
import type { OutBase } from '../models/OutBase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DiagnosticsService {
    /**
     * Get Logs
     * @returns LogsOut Successful Response
     * @throws ApiError
     */
    public static getLogs(): CancelablePromise<LogsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/logs',
        });
    }
    /**
     * Export Logs
     * @returns LogExportOut Successful Response
     * @throws ApiError
     */
    public static exportLogs(): CancelablePromise<LogExportOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/logs/export',
        });
    }
    /**
     * Write Client Log
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static writeClientLog(
        requestBody: ClientLogIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/logs/frontend',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
