import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import ScannerView from '../views/ScannerView.vue'
import BulkUploadView from '../views/BulkUploadView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/scanner',
      name: 'scanner',
      component: ScannerView
    },
    {
      path: '/bulk-upload',
      name: 'bulk-upload',
      component: BulkUploadView
    }
  ]
})

export default router
