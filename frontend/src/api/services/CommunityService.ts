/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountCreateOut } from '../models/AccountCreateOut';
import type { AccountIdIn } from '../models/AccountIdIn';
import type { AccountReorderIn } from '../models/AccountReorderIn';
import type { AccountsOut } from '../models/AccountsOut';
import type { AccountUpdateIn } from '../models/AccountUpdateIn';
import type { ActivityQueryIn } from '../models/ActivityQueryIn';
import type { CommunityActivityOut } from '../models/CommunityActivityOut';
import type { OutBase } from '../models/OutBase';
import type { QrCheckIn } from '../models/QrCheckIn';
import type { QrCheckOut } from '../models/QrCheckOut';
import type { QrCreateOut } from '../models/QrCreateOut';
import type { QrSaveIn } from '../models/QrSaveIn';
import type { SettingsData } from '../models/SettingsData';
import type { SettingsOut } from '../models/SettingsOut';
import type { StatusOut } from '../models/StatusOut';
import type { TaygedoLoginIn } from '../models/TaygedoLoginIn';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CommunityService {
    /**
     * List Accounts
     * @returns AccountsOut Successful Response
     * @throws ApiError
     */
    public static listAccounts(): CancelablePromise<AccountsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/accounts',
        });
    }
    /**
     * Create Account
     * @returns AccountCreateOut Successful Response
     * @throws ApiError
     */
    public static createAccount(): CancelablePromise<AccountCreateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/accounts',
        });
    }
    /**
     * Update Account
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static updateAccount(
        requestBody: AccountUpdateIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/accounts/update',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Account
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static deleteAccount(
        requestBody: AccountIdIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/accounts/delete',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Reorder Accounts
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static reorderAccounts(
        requestBody: AccountReorderIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/accounts/reorder',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Settings
     * @returns SettingsOut Successful Response
     * @throws ApiError
     */
    public static getSettings(): CancelablePromise<SettingsOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/settings',
        });
    }
    /**
     * Update Settings
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static updateSettings(
        requestBody: SettingsData,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/settings',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Status
     * @returns StatusOut Successful Response
     * @throws ApiError
     */
    public static getStatus(): CancelablePromise<StatusOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/status',
        });
    }
    /**
     * Manual Sign
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static manualSign(): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/sign',
        });
    }
    /**
     * Query Activity
     * @param requestBody
     * @returns CommunityActivityOut Successful Response
     * @throws ApiError
     */
    public static queryActivity(
        requestBody: ActivityQueryIn,
    ): CancelablePromise<CommunityActivityOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/activity',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Qr
     * @param provider
     * @returns QrCreateOut Successful Response
     * @throws ApiError
     */
    public static createQr(
        provider: 'miyoushe' | 'skland',
    ): CancelablePromise<QrCreateOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/{provider}/qr/create',
            path: {
                'provider': provider,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Check Qr
     * @param provider
     * @param requestBody
     * @returns QrCheckOut Successful Response
     * @throws ApiError
     */
    public static checkQr(
        provider: 'miyoushe' | 'skland',
        requestBody: QrCheckIn,
    ): CancelablePromise<QrCheckOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/{provider}/qr/check',
            path: {
                'provider': provider,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Save Qr
     * @param provider
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static saveQr(
        provider: 'miyoushe' | 'skland',
        requestBody: QrSaveIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/{provider}/qr/save',
            path: {
                'provider': provider,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Login Taygedo
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static loginTaygedo(
        requestBody: TaygedoLoginIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/login/taygedo',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
