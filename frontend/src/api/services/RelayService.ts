/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OutBase } from '../models/OutBase';
import type { RelayCommandAcceptedOut } from '../models/RelayCommandAcceptedOut';
import type { RelayCommandIn } from '../models/RelayCommandIn';
import type { RelayCommandStatusOut } from '../models/RelayCommandStatusOut';
import type { RelayNodesOut } from '../models/RelayNodesOut';
import type { RelayPollIn } from '../models/RelayPollIn';
import type { RelayPollOut } from '../models/RelayPollOut';
import type { RelayResultIn } from '../models/RelayResultIn';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class RelayService {
    /**
     * Relay Command
     * @param requestBody
     * @returns RelayCommandAcceptedOut Successful Response
     * @throws ApiError
     */
    public static relayCommand(
        requestBody: RelayCommandIn,
    ): CancelablePromise<RelayCommandAcceptedOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/relay/command',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Relay Poll
     * @param requestBody
     * @returns RelayPollOut Successful Response
     * @throws ApiError
     */
    public static relayPoll(
        requestBody: RelayPollIn,
    ): CancelablePromise<RelayPollOut> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/relay/poll',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Relay Result
     * @param requestBody
     * @returns OutBase Successful Response
     * @throws ApiError
     */
    public static relayResult(
        requestBody: RelayResultIn,
    ): CancelablePromise<OutBase> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/relay/result',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Relay Nodes
     * @returns RelayNodesOut Successful Response
     * @throws ApiError
     */
    public static relayNodes(): CancelablePromise<RelayNodesOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/relay/nodes',
        });
    }
    /**
     * Relay Command Status
     * @param commandId
     * @returns RelayCommandStatusOut Successful Response
     * @throws ApiError
     */
    public static relayCommandStatus(
        commandId: string,
    ): CancelablePromise<RelayCommandStatusOut> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/relay/commands/{command_id}',
            path: {
                'command_id': commandId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
