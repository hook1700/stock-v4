<template>
  <el-container style="height: 100vh;">
    <el-aside width="200px" style="background: #1e1e2d; color: #fff;">
      <div style="padding: 20px; font-size: 18px; font-weight: bold; text-align: center;">
        📈 股票分析系统
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#1e1e2d"
        text-color="#b0b0c3"
        active-text-color="#fff"
        style="border: none;"
      >
        <el-menu-item index="/stocks">
          <el-icon><Document /></el-icon>
          <span>股票列表</span>
        </el-menu-item>
        <el-menu-item index="/strategies">
          <el-icon><TrendCharts /></el-icon>
          <span>策略结果</span>
        </el-menu-item>
        <el-menu-item index="/records">
          <el-icon><Calendar /></el-icon>
          <span>每日记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="padding: 20px; background: #f0f2f5;">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>