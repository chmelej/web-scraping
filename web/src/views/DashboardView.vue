<template>
  <div>
    <h2 class="text-2xl font-bold mb-6">Dashboard</h2>

    <div v-if="loading" class="text-gray-500">Loading...</div>
    <div v-else-if="error" class="text-red-500">{{ error }}</div>

    <div v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="bg-white p-6 rounded-lg shadow border border-gray-200">
          <h3 class="text-gray-500 text-sm font-medium">Total URLs in Queue</h3>
          <p class="text-3xl font-bold text-gray-800 mt-2">{{ stats.total_urls }}</p>
        </div>

        <div class="bg-white p-6 rounded-lg shadow border border-gray-200">
          <h3 class="text-gray-500 text-sm font-medium">Pending URLs</h3>
          <p class="text-3xl font-bold text-blue-600 mt-2">{{ stats.pending_queue }}</p>
        </div>

        <div class="bg-white p-6 rounded-lg shadow border border-gray-200">
          <h3 class="text-gray-500 text-sm font-medium">Failed URLs</h3>
          <p class="text-3xl font-bold text-red-600 mt-2">{{ stats.status_breakdown.failed || 0 }}</p>
        </div>
      </div>

      <div class="bg-white p-6 rounded-lg shadow border border-gray-200">
        <h3 class="text-lg font-bold mb-4">Recent Velocity (Last 7 Days)</h3>
        <table class="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Scrapes</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Successful (200 OK)</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="day in stats.recent_velocity" :key="day.date">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ day.date }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ day.total }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-medium">{{ day.success }}</td>
            </tr>
            <tr v-if="stats.recent_velocity.length === 0">
              <td colspan="3" class="px-6 py-4 text-center text-gray-500">No scrape data available for the last 7 days.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getDashboardInfo } from '../services/api';

const loading = ref(true);
const error = ref('');
const stats = ref<any>({});

onMounted(async () => {
  try {
    stats.value = await getDashboardInfo();
  } catch (err: any) {
    error.value = 'Failed to load dashboard data. Is the API running?';
    console.error(err);
  } finally {
    loading.value = false;
  }
});
</script>
