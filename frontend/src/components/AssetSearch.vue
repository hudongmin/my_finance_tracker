<template>
  <div class="search-container">
    <label for="asset-search">搜索金融资产</label>
    <input
      id="asset-search"
      type="text"
      v-model="searchQuery"
      @input="handleInput"
      placeholder="输入股票/ETF代码、名称，或6位基金代码"
      autocomplete="off"
    />
    <div v-if="isLoading" class="loading-spinner"></div>
    <ul v-if="searchResults.length > 0" class="results-list">
      <li 
        v-for="item in searchResults" 
        :key="item.symbol" 
        @click="selectAsset(item)"
        class="result-item"
      >
        <div class="item-symbol">{{ item.symbol }}</div>
        <div class="item-name">{{ item.name }}</div>
        <div class="item-region">[{{ item.type }} / {{ item.region }}]</div>
      </li>
    </ul>
    <div v-if="!isLoading && searchQuery && searchResults.length === 0" class="no-results">
      没有找到匹配的结果。
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

// 定义组件状态
const searchQuery = ref('');      // 搜索输入框的内容
const searchResults = ref([]);    // 从API获取的搜索结果列表
const isLoading = ref(false);     // 是否正在加载数据
let debounceTimer = null;         // 用于实现防抖的计时器

// 定义组件可以向父组件发送的事件
const emit = defineEmits(['asset-selected']);

// 处理用户输入
const handleInput = () => {
  // 清除上一次的计时器
  clearTimeout(debounceTimer);
  // 如果输入为空，则清空结果
  if (!searchQuery.value.trim()) {
    searchResults.value = [];
    return;
  }
  // 设置一个新的计时器，500毫秒后执行搜索
  // 这就是“防抖”，避免用户每打一个字就发送一次请求
  debounceTimer = setTimeout(() => {
    performSearch();
  }, 500);
};

// 执行搜索的异步函数
const performSearch = async () => {
  isLoading.value = true;
  searchResults.value = [];
  try {
    // 调用我们后端的 /api/search 接口
    const response = await axios.get('http://127.0.0.1:5001/api/search', {
      params: {
        q: searchQuery.value
      }
    });
    // 将返回的数据（后端已经处理成我们需要的格式）赋值给 searchResults
    searchResults.value = response.data;
  } catch (error) {
    console.error("搜索失败:", error);
    // 这里可以添加更友好的用户错误提示
  } finally {
    isLoading.value = false;
  }
};

// 当用户点击选择某个资产时
const selectAsset = (asset) => {
  console.log('已选择:', asset);
  // 清空搜索框和结果列表
  searchQuery.value = '';
  searchResults.value = [];
  // 通过 emit 发送一个名为 'asset-selected' 的事件给父组件
  // 并把选中的资产对象作为参数传递出去
  emit('asset-selected', asset);
};
</script>

<style scoped>
.search-container {
  font-family: sans-serif;
  position: relative;
  width: 350px;
}
label {
  font-weight: bold;
  display: block;
  margin-bottom: 8px;
}
input {
  width: 100%;
  padding: 10px;
  font-size: 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
.results-list {
  list-style: none;
  padding: 0;
  margin: 4px 0 0 0;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #fff;
  position: absolute;
  width: 100%;
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
}
.result-item {
  padding: 10px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-item:last-child {
  border-bottom: none;
}
.result-item:hover {
  background-color: #f0f0f0;
}
.item-symbol {
  font-weight: bold;
  color: #0056b3;
}
.item-name {
  flex-grow: 1;
  padding: 0 10px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-region {
  font-size: 0.8em;
  color: #777;
}
.no-results {
  padding: 10px;
  color: #777;
}
.loading-spinner {
  /* 一个简单的加载动画 */
  border: 4px solid rgba(0, 0, 0, 0.1);
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border-left-color: #007bff;
  animation: spin 1s ease infinite;
  position: absolute;
  right: 10px;
  top: 32px; /* 调整位置以适应输入框 */
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>