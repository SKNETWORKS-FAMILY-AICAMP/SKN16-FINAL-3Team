import { Fragment } from 'react'
import { Link } from 'react-router-dom'

type AuthLink = {
  to: string
  label: string
}

type AuthLinkGroupProps = {
  links: AuthLink[]
  className?: string
}

/**
 * 인증 관련 페이지 하단 링크를 통일된 디자인으로 렌더링합니다.
 */
export default function AuthLinkGroup({ links, className = '' }: AuthLinkGroupProps) {
  if (!links.length) return null

  return (
    <div className={`flex items-center justify-center text-sm ${className}`.trim()}>
      {links.map((link, index) => (
        <Fragment key={link.to}>
          {index > 0 && <span className="mx-3 text-primary-300">|</span>}
          <Link to={link.to} className="text-primary-600 hover:text-primary-700 font-medium">
            {link.label}
          </Link>
        </Fragment>
      ))}
    </div>
  )
}



