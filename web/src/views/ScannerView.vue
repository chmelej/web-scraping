<template>
  <div>
    <h2 class="text-2xl font-bold mb-6">Single URL Scanner</h2>

    <div class="bg-white p-6 rounded-lg shadow border border-gray-200 mb-6">
      <form @submit.prevent="searchUrl" class="flex gap-4">
        <input
          v-model="urlInput"
          type="text"
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
          <p class="text-sm text-gray-500">Normalized URL</p>
          <p class="font-medium break-all">{{ urlInfo.normalized_url }}</p>
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

      <div v-if="urlInfo.extracted_data" class="border-t border-gray-200 pt-4 mb-6">
        <h4 class="font-semibold mb-2">Extracted Data</h4>
        <pre class="bg-gray-50 p-4 rounded text-xs overflow-auto max-h-64">{{ JSON.stringify(urlInfo.extracted_data, null, 2) }}</pre>
      </div>

      <div class="border-t border-gray-200 pt-4 mb-6" v-if="urlInfo.history && urlInfo.history.length > 0">
        <h4 class="font-semibold mb-4">Scraping History</h4>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200 border">
            <thead class="bg-gray-50">
              <tr>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status Code</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Processing</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error</th>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Raw HTML</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="historyRow in urlInfo.history" :key="historyRow.result_id">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ formatDate(historyRow.scraped_at) }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" :class="{'text-red-600': historyRow.status_code >= 400, 'text-green-600': historyRow.status_code == 200}">
                  {{ historyRow.status_code || '-' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ historyRow.processing_status }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-500 truncate max-w-[200px]" :title="historyRow.error_message">{{ historyRow.error_message || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <a :href="`/api/v1/queue/html/${historyRow.result_id}`" target="_blank" class="text-blue-600 hover:text-blue-900 flex items-center">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                    View HTML
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="mt-6 flex justify-end gap-3">
        <button @click="openManualUpdate" class="bg-gray-100 text-gray-700 px-4 py-2 rounded text-sm hover:bg-gray-200 font-medium border border-gray-300">
          Manual Update
        </button>
        <button @click="enqueue" :disabled="enqueuing" class="bg-blue-100 text-blue-700 px-4 py-2 rounded text-sm hover:bg-blue-200 font-medium">
          {{ enqueuing ? 'Adding...' : 'Re-queue (Priority 10)' }}
        </button>
      </div>
    </div>

    <!-- Manual Update Modal -->
    <div v-if="showManualModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white p-6 rounded-lg shadow-xl w-full max-w-4xl mx-4">
        <h3 class="text-xl font-bold mb-4">Manual Update for {{ urlInfo?.url || urlInput }}</h3>
        <p class="text-sm text-gray-600 mb-4">
          Paste the raw HTML source code of the page here. This will save the content as a successful scrape result and set the queue status to manual.
        </p>

        <div v-if="manualUpdateError" class="mb-4 bg-red-50 text-red-700 p-3 rounded text-sm border-l-4 border-red-500">
          {{ manualUpdateError }}
        </div>

        <textarea
          v-model="manualHtml"
          @paste="handlePaste"
          rows="15"
          placeholder="Paste webpage content here (Ctrl+V) or raw HTML..."
          class="w-full p-3 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm mb-4"
        ></textarea>

        <div class="flex justify-end gap-3">
          <button @click="closeManualUpdate" class="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 disabled:opacity-50" :disabled="submittingManual">
            Cancel
          </button>
          <button @click="submitManualUpdate" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center" :disabled="submittingManual || !manualHtml.trim()">
            <svg v-if="submittingManual" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ submittingManual ? 'Saving...' : 'Save Manual Update' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { getUrlInfo, enqueueUrl, manualUpdateUrl } from '../services/api';

const route = useRoute();

const urlInput = ref('');
const loading = ref(false);
const enqueuing = ref(false);
const error = ref('');
const isNotFound = ref(false);
const enqueueSuccess = ref('');
const urlInfo = ref<any>(null);

const showManualModal = ref(false);
const manualHtml = ref('');
const submittingManual = ref(false);
const manualUpdateError = ref('');

const handlePaste = (e: ClipboardEvent) => {
  if (e.clipboardData) {
    const htmlData = e.clipboardData.getData('text/html');
    if (htmlData) {
      e.preventDefault();
      manualHtml.value = htmlData;
    }
  }
};

const searchUrl = async () => {
  let url = urlInput.value.trim();
  if (url && !/^https?:\/\//i.test(url)) {
    url = 'https://' + url;
    urlInput.value = url;
  }

  loading.value = true;
  error.value = '';
  isNotFound.value = false;
  enqueueSuccess.value = '';
  urlInfo.value = null;

  try {
    const data = await getUrlInfo(url);
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

const openManualUpdate = () => {
  manualHtml.value = '';
  manualUpdateError.value = '';
  showManualModal.value = true;
};

const closeManualUpdate = () => {
  showManualModal.value = false;
};

const submitManualUpdate = async () => {
  if (!manualHtml.value.trim()) return;

  submittingManual.value = true;
  manualUpdateError.value = '';

  try {
    const targetUrl = urlInfo.value?.url || urlInput.value;
    const queueId = urlInfo.value?.queue_id; // Will be undefined if it doesn't exist yet, which is fine

    await manualUpdateUrl(targetUrl, manualHtml.value, queueId);

    // Close modal and refresh data
    showManualModal.value = false;
    enqueueSuccess.value = 'Manual update successful!';

    setTimeout(() => {
      searchUrl();
    }, 500);

  } catch (err: any) {
    manualUpdateError.value = err.response?.data?.detail || 'Failed to submit manual update.';
    console.error(err);
  } finally {
    submittingManual.value = false;
  }
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
};

onMounted(() => {
  if (route.query.url) {
    urlInput.value = route.query.url as string;
    searchUrl();
  }
});
</script>
