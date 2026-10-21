/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WikiSectionOut } from './WikiSectionOut';
export type WikiEntryDataOut = {
    kind: 'character' | 'weapon' | 'equipSuit' | 'dungeon' | 'enemy';
    id: string;
    name: string;
    subtitle?: string;
    icon?: string;
    tags?: Array<string>;
    sections?: Array<WikiSectionOut>;
};

