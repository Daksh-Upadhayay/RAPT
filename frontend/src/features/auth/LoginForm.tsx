import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { Button, ErrorNotice, Field, Input } from '../../ui'
import { useLogin } from './hooks'

function loginError(error: unknown): string {
  if (error instanceof ApiError && (error.status === 401 || error.status === 429)) return error.message
  return error instanceof Error ? error.message : 'Signing in failed. Try again.'
}

export function LoginForm({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const signIn = useLogin()

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    signIn.mutate({ email: email.trim(), password }, { onSuccess: onSignedIn })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field id="email" label="Email">
        <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field id="password" label="Password">
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      {signIn.isError && <ErrorNotice error={new Error(loginError(signIn.error))} />}
      <Button type="submit" variant="primary" className="w-full" loading={signIn.isPending} disabled={!email.trim() || !password}>
        Sign in
      </Button>
    </form>
  )
}
