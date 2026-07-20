<template>
  <div>
    <h2 class="text-2xl font-bold mb-6">Single URL Scanner</h2>

    <div class="bg-white p-6 rounded-lg shadow border border-gray-200 mb-6">
      <form @submit.prevent="searchUrl" class="flex gap-4">
        <input
          v-model="urlInput"
          type="url"
          required
          placeholder="https://www.example.com"
          class="flex-1 px-4 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          :disabled="loading"
          class="bg-blue-600 text-white px-6 py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {{ loading ? 'Searching...' : 'Check URL' }}
        </button>
      </form>
    </div>

    <div v-if="error" class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
      <div class="flex">
        <div class="ml-3">
          <p class="text-sm text-yellow-700">
            {{ error }}
          </p>
          <div class="mt-4" v-if="isNotFound">
             <button @click="enqueue" :disabled="enqueuing" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
               {{ enqueuing ? 'Adding...' : 'Add to Queue (Priority 10)' }}
             </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="enqueueSuccess" class="bg-green-50 border-l-4 border-green-400 p-4 mb-6">
      <p class="text-sm text-green-700">{{ enqueueSuccess }}</p>
    </div>

    <div v-if="urlInfo" class="bg-white p-6 rounded-lg shadow border border-gray-200">
      <div class="flex justify-between items-start mb-4">
        <h3 class="text-lg font-bold">URL Information</h3>
        <span class="px-3 py-1 rounded-full text-xs font-semibold"
          :class="{
            'bg-green-100 text-green-800': urlInfo.status === 'completed',
            'bg-yellow-100 text-yellow-800': urlInfo.status === 'pending',
            'bg-blue-100 text-blue-800': urlInfo.status === 'processing',
            'bg-red-100 text-red-800': urlInfo.status === 'failed',
            'bg-gray-100 text-gray-800': !urlInfo.status
          }">
          {{ urlInfo.status || 'unknown' }}
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-y-4 gap-x-8 mb-6">
        <div>
          <p class="text-sm text-gray-500">URL</p>
          <p class="font-medium break-all">{{ urlInfo.url }}</p>
        </div>
        <div>
          <p class="text-sm text-gray-500">Site Type</p>
          <p class="font-medium">{{ urlInfo.site_type }}</p>
        </div>
        <div>
          <p class="text-sm text-gray-500">Added to Queue</p>
          <p class="font-medium">{{ formatDate(urlInfo.added_at) }}</p>
        </div>
        <div>
          <p class="text-sm text-gray-500">Latest Scrape</p>
          <p class="font-medium">{{ formatDate(urlInfo.latest_scraped_at) }}</p>
        </div>
        <div>
          <p class="text-sm text-gray-500">Latest Status Code</p>
          <p class="font-medium" :class="{'text-red-600': urlInfo.latest_status_code >= 400}">{{ urlInfo.latest_status_code || '-' }}</p>
        </div>
        <div>
          <p class="text-sm text-gray-500">Error</p>
          <p class="font-medium text-red-600">{{ urlInfo.latest_error || '-' }}</p>
        </div>
      </div>

      <div class="border-t border-gray-200 pt-4 mb-6">
        <h4 class="font-semibold mb-2">NFS Artifacts (Latest)</h4>
        <ul class="space-y-2 text-sm">
          <li><strong>HTML:</strong> <span class="text-gray-600 font-mono text-xs break-all">{{ urlInfo.latestHtmlLink || 'N/A' }}</span></li>
          <li><strong>Markdown:</strong> <span class="text-gray-600 font-mono text-xs break-all">{{ urlInfo.latestMarkdownLink || 'N/A' }}</span></li>
          <li><strong>Screenshot:</strong> <span class="text-gray-600 font-mono text-xs break-all">{{ urlInfo.latestScreenshotLink || 'N/A' }}</span></li>
        </ul>
      </div>

      <div v-if="urlInfo.extracted_data" class="border-t border-gray-200 pt-4">
        <h4 class="font-semibold mb-2">Extracted Data</h4>
        <pre class="bg-gray-50 p-4 rounded text-xs overflow-auto max-h-64">{{ JSON.stringify(urlInfo.extracted_data, null, 2) }}</pre>
      </div>

      <div class="mt-6 text-right">
        <button @click="enqueue" :disabled="enqueuing" class="bg-blue-100 text-blue-700 px-4 py-2 rounded text-sm hover:bg-blue-200 font-medium">
          {{ enqueuing ? 'Adding...' : 'Re-queue (Priority 10)' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { getUrlInfo, enqueueUrl } from '../services/api';

const urlInput = ref('');
const loading = ref(false);
const enqueuing = ref(false);
const error = ref('');
const isNotFound = ref(false);
const enqueueSuccess = ref('');
const urlInfo = ref<any>(null);

const searchUrl = async () => {
  loading.value = true;
  error.value = '';
  isNotFound.value = false;
  enqueueSuccess.value = '';
  urlInfo.value = null;

  try {
    const data = await getUrlInfo(urlInput.value);
    urlInfo.value = data;
  } catch (err: any) {
    if (err.response && err.response.status === 404) {
      error.value = 'URL not found in the database. You can add it to the queue to be scraped.';
      isNotFound.value = true;
    } else {
      error.value = 'An error occurred while fetching URL info.';
      console.error(err);
    }
  } finally {
    loading.value = false;
  }
};

const enqueue = async () => {
  enqueuing.value = true;
  error.value = '';
  enqueueSuccess.value = '';

  try {
    const targetUrl = urlInfo.value?.url || urlInput.value;
    const result = await enqueueUrl(targetUrl, 10);
    enqueueSuccess.value = result.message;

    // Refresh info if we were just viewing it
    if (urlInfo.value) {
      setTimeout(() => {
        searchUrl();
      }, 1000);
    }
  } catch (err: any) {
    error.value = 'Failed to add URL to queue.';
    console.error(err);
  } finally {
    enqueuing.value = false;
  }
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
};
</script>
