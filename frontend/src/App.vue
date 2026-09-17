<template>
  <router-view />
</template>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f5f7fa;
  color: #303133;
}
.page { padding: 20px 24px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0 0 16px; }
.page-card { background: #fff; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.muted { color: #909399; font-size: 12px; }
</style>
