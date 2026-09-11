/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type GachaRecord = {
    game: 'genshin' | 'starrail' | 'zzz' | 'wuthering' | 'arknights' | 'endfield';
    playerUid: string;
    id: string;
    poolType: string;
    poolName?: string;
    name: string;
    itemId?: string;
    itemType?: string;
    rarity: number;
    time: string;
    timezone?: number;
    lang?: string;
    isFree?: boolean;
    kind?: string;
};

