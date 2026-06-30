'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import CardNav from '@/components/CardNav';
import { Logo } from '@/components/logo';
import { authClient } from '@/lib/auth-client';

export function SiteNav() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    authClient.getSession().then(({ data }) => {
      setLoggedIn(!!data?.user);
    });
  }, []);

  return (
    <CardNav
      logo={
        <Link href="/" className="flex items-center gap-1.5 text-white no-underline">
          Open
          <Logo className="h-7 w-7 text-white" />
          Human
        </Link>
      }
      items={[
        {
          label: 'Product',
          bgColor: '#3e4229',
          textColor: '#ffffff',
          links: [
            { label: 'Features', href: '#', ariaLabel: 'Features' },
            { label: 'Changelog', href: '#', ariaLabel: 'Changelog' },
          ],
        },
        {
          label: 'Resources',
          bgColor: '#656b37',
          textColor: '#ffffff',
          links: [
            { label: 'Docs', href: '#', ariaLabel: 'Documentation' },
            {
              label: 'GitHub',
              href: 'https://github.com/openhuman/openhuman',
              ariaLabel: 'GitHub',
            },
          ],
        },
        {
          label: 'Company',
          bgColor: '#1a1717',
          textColor: '#e8ecd0',
          links: [
            { label: 'About', href: '#', ariaLabel: 'About' },
            { label: 'Blog', href: '#', ariaLabel: 'Blog' },
          ],
        },
      ]}
      baseColor="#1a1717"
      menuColor="#e8ecd0"
      buttonBgColor="#ffffff"
      buttonTextColor="#1a1717"
      ctaLabel={loggedIn ? 'Dashboard' : 'Get Started'}
      ctaHref={loggedIn ? '/dashboard' : '/signup'}
    />
  );
}
