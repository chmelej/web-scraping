<template>
  <div>
    <h2 class="text-2xl font-bold mb-6">Bulk Upload URLs</h2>

    <div class="bg-white p-6 rounded-lg shadow border border-gray-200">
      <p class="text-gray-600 mb-6">
        Upload a <code>.txt</code> or <code>.csv</code> file containing URLs (one per line).
        All valid URLs will be added to the queue with a default priority of 5.
      </p>

      <form @submit.prevent="uploadFile" class="space-y-6">
        <div class="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center hover:bg-gray-50 transition-colors cursor-pointer relative">
          <input
            type="file"
            accept=".txt,.csv"
            @change="handleFileChange"
            class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div v-if="!selectedFile">
            <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <p class="mt-1 text-sm text-gray-600">Click or drag file here to upload</p>
          </div>
          <div v-else class="text-blue-600 font-medium">
            Selected: {{ selectedFile.name }} ({{ (selectedFile.size / 1024).toFixed(2) }} KB)
          </div>
        </div>

        <div v-if="error" class="text-red-500 text-sm">{{ error }}</div>

        <div v-if="result" class="bg-green-50 p-4 rounded text-green-800 border border-green-200">
          <p class="font-bold">{{ result.message }}</p>
          <ul class="list-disc pl-5 mt-2 text-sm">
            <li>Added/Updated: {{ result.added_count }}</li>
            <li>Skipped/Invalid: {{ result.skipped_or_invalid_count }}</li>
          </ul>
        </div>

        <div>
          <button
            type="submit"
            :disabled="!selectedFile || uploading"
            class="bg-blue-600 text-white px-6 py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ uploading ? 'Uploading and Processing...' : 'Upload URLs' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { bulkEnqueueUrls } from '../services/api';

const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const error = ref('');
const result = ref<any>(null);

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
    error.value = '';
    result.value = null;
  }
};

const uploadFile = async () => {
  if (!selectedFile.value) return;

  uploading.value = true;
  error.value = '';
  result.value = null;

  try {
    const data = await bulkEnqueueUrls(selectedFile.value);
    result.value = data;
    selectedFile.value = null; // reset
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'An error occurred during upload.';
    console.error(err);
  } finally {
    uploading.value = false;
  }
};
</script>
