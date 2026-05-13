import { useState, useCallback } from 'react'
import { ChevronRight, FileText } from 'lucide-react'

function ReferencePanel({ sources = [] }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const handleToggle = useCallback(() => {
    setIsExpanded(prev => !prev)
  }, [])

  if (!sources || sources.length === 0) return null

  return (
    <div className="reference-panel">
      <div className="reference-toggle" onClick={handleToggle}>
        <ChevronRight size={14} className={isExpanded ? 'rotated' : ''} />
        参考来源 ({sources.length})
      </div>
      {isExpanded && (
        <div className="reference-sources">
          {sources.map((ref, idx) => (
            <div key={idx} className="reference-source">
              <div className="source-title">
                <FileText
                  size={12}
                  style={{ marginRight: 4, verticalAlign: 'middle' }}
                />
                {ref.title || ref.filename || '参考来源'}
              </div>
              <div className="source-snippet">{ref.snippet || ref.content || ''}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ReferencePanel
