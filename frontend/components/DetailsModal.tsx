'use client'

import Modal from './Modal'

interface DetailsModalProps {
  isOpen: boolean
  onClose: () => void
  project: {
    token: string
    title: string
    owner_email: string
    metadata?: {
      id: number
      total_pages?: number
      total_products?: number
    }
    last_run?: {
      pages: number
      status: string
      start_time: string
      run_token?: string
    } | null
  }
}

export default function DetailsModal({
  isOpen,
  onClose,
  project,
}: DetailsModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${project.title} - Project Details`}
    >
      <div className="space-y-6">
        <div className="bg-slate-700/20 rounded-lg p-4 border border-slate-700">
          <h3 className="font-semibold text-white mb-3">Project Information</h3>
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-slate-400 mb-1">Project Title</p>
              <p className="text-slate-100 font-medium">{project.title}</p>
            </div>
            <div>
              <p className="text-slate-400 mb-1">Owner</p>
              <p className="text-slate-100 font-medium">{project.owner_email}</p>
            </div>
            <div>
              <p className="text-slate-400 mb-1">Project Token</p>
              <p className="text-slate-100 font-mono bg-slate-800 p-2 rounded break-all">
                {project.token}
              </p>
            </div>
          </div>
        </div>

        {project.metadata && (
          <div className="bg-slate-700/20 rounded-lg p-4 border border-slate-700">
            <h3 className="font-semibold text-white mb-3">Metadata</h3>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-slate-400 mb-1">Total Pages (Target)</p>
                <p className="text-slate-100 font-medium">{project.metadata.total_pages || 'Not set'}</p>
              </div>
              <div>
                <p className="text-slate-400 mb-1">Total Products</p>
                <p className="text-slate-100 font-medium">{project.metadata.total_products || 'Not set'}</p>
              </div>
            </div>
          </div>
        )}

        {project.last_run && (
          <div className="bg-slate-700/20 rounded-lg p-4 border border-slate-700">
            <h3 className="font-semibold text-white mb-3">Last Run Information</h3>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-slate-400 mb-1">Run Token</p>
                <p className="text-slate-100 font-mono bg-slate-800 p-2 rounded break-all">
                  {project.last_run.run_token || 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-slate-400 mb-1">Status</p>
                <span className="inline-block px-3 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  {project.last_run.status.toUpperCase()}
                </span>
              </div>
              <div>
                <p className="text-slate-400 mb-1">Pages Scraped</p>
                <p className="text-slate-100">{project.last_run.pages}</p>
              </div>
              <div>
                <p className="text-slate-400 mb-1">Started At</p>
                <p className="text-slate-100">
                  {new Date(project.last_run.start_time).toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="bg-slate-700/20 rounded-lg p-4 border border-slate-700">
          <h3 className="font-semibold text-white mb-3">Data Files</h3>
          <p className="text-sm text-slate-400 mb-3">
            Data is stored on the server at:
          </p>
          <p className="text-xs font-mono bg-slate-800 p-2 rounded text-slate-300">
            data_{project.token}.json
          </p>
        </div>
      </div>
    </Modal>
  )
}
