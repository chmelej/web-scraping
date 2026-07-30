<template>
  <div class="min-h-screen bg-gray-100 flex">
    <!-- Sidebar -->
    <aside class="w-64 bg-white border-r border-gray-200">
      <div class="h-16 flex items-center px-6 border-b border-gray-200">
        <h1 class="text-xl font-bold text-blue-600">Web Scraper</h1>
      </div>
      <nav class="p-4 space-y-2">
        <router-link to="/" class="block px-4 py-2 rounded text-gray-700 hover:bg-blue-50 hover:text-blue-600" exact-active-class="bg-blue-50 text-blue-600 font-semibold">
          Dashboard
        </router-link>
        <router-link to="/scanner" class="block px-4 py-2 rounded text-gray-700 hover:bg-blue-50 hover:text-blue-600" active-class="bg-blue-50 text-blue-600 font-semibold">
          Single URL Scanner
        </router-link>
        <router-link to="/bulk-upload" class="block px-4 py-2 rounded text-gray-700 hover:bg-blue-50 hover:text-blue-600" active-class="bg-blue-50 text-blue-600 font-semibold">
          Bulk Upload
        </router-link>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 p-8">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
//
</script>
