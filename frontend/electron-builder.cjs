/** 独立打包，不配置组织远端或自动更新；Release 上传由 GitHub Actions 负责。 */
module.exports = {
  appId: 'independent.bettermas.community',
  productName: '更好的MAS游戏社区版',
  executableName: 'BetterMASCommunity',
  directories: { output: 'out' },
  files: ['dist-electron/**/*', 'package.json', '!node_modules/**/*'],
  extraResources: [
    { from: '../build/backend/community-backend', to: 'backend' },
    { from: 'dist', to: 'renderer' },
    { from: '../LICENSE', to: 'LICENSE' },
    { from: '../NOTICE.md', to: 'NOTICE.md' },
    { from: '../docs', to: 'docs' },
    { from: '../README.md', to: 'README.md' },
    { from: 'src/assets/community-notes/ATTRIBUTION.md', to: 'community-notes-ATTRIBUTION.md' },
    {
      from: 'src/assets/community-notes/standalone-manifest.json',
      to: 'community-notes-manifest.json',
    },
  ],
  npmRebuild: false,
  asar: true,
  win: {
    icon: 'assets/community.ico',
    target: [
      { target: 'zip', arch: ['x64'] },
      { target: 'portable', arch: ['x64'] },
    ],
    requestedExecutionLevel: 'asInvoker',
  },
  artifactName: 'BetterMASCommunity-${version}-win-${arch}.${ext}',
  publish: null,
}
