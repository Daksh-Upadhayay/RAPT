import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { inviteMember, listTeam, resetMemberPassword, teamKeys, updateMember } from '../../api/team'
import { dateTime } from '../../lib/format'
import type { PasswordIssued, TeamMember, UserRole } from '../../types'
import { Button, ErrorNotice, Field, Input, Loading, Select, Sheet, Tag } from '../../ui'
import { useSession } from '../auth'

function OneTimePassword({ issued, onDone }: { issued: PasswordIssued; onDone: () => void }) {
  const [copied, setCopied] = useState(false)
  return (
    <div role="status" className="rounded-label border border-accent-deep bg-accent-wash p-4">
      <p className="font-semibold">One-time password for {issued.member.email}</p>
      <p className="mt-1 text-small text-ink-2">Share it privately. It isn't shown again; reset it if it gets lost.</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code className="rounded-label border border-line bg-paper px-3 py-1.5 font-mono text-body">{issued.one_time_password}</code>
        <Button
          size="sm"
          onClick={() => {
            void navigator.clipboard?.writeText(issued.one_time_password).then(() => setCopied(true))
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  )
}

function InviteForm({ onIssued }: { onIssued: (issued: PasswordIssued) => void }) {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<UserRole>('reviewer')
  const invite = useMutation({
    mutationFn: inviteMember,
    onSuccess: (issued) => {
      void queryClient.invalidateQueries({ queryKey: teamKeys.all })
      setEmail('')
      setName('')
      onIssued(issued)
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    invite.mutate({ email: email.trim(), name: name.trim(), role })
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-[1fr_1fr_10rem_auto] sm:items-end">
      <Field id="invite-name" label="Name">
        <Input id="invite-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
      </Field>
      <Field id="invite-email" label="Email">
        <Input id="invite-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </Field>
      <Field id="invite-role" label="Role">
        <Select id="invite-role" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
          <option value="reviewer">Reviewer</option>
          <option value="admin">Admin</option>
        </Select>
      </Field>
      <Button type="submit" variant="primary" loading={invite.isPending} disabled={!email.trim() || !name.trim()}>
        Add member
      </Button>
      {invite.isError && (
        <div className="sm:col-span-4">
          <ErrorNotice error={invite.error} />
        </div>
      )}
    </form>
  )
}

function MemberRow({ member, isMe, onIssued }: { member: TeamMember; isMe: boolean; onIssued: (issued: PasswordIssued) => void }) {
  const queryClient = useQueryClient()
  const refresh = () => void queryClient.invalidateQueries({ queryKey: teamKeys.all })
  const update = useMutation({ mutationFn: (data: Parameters<typeof updateMember>[1]) => updateMember(member.id, data), onSuccess: refresh })
  const reset = useMutation({ mutationFn: () => resetMemberPassword(member.id), onSuccess: onIssued })

  return (
    <tr className="border-b border-line align-top last:border-0">
      <td className="py-3 pr-4">
        <p className="font-semibold">
          {member.name} {isMe && <span className="font-normal text-ink-3">(you)</span>}
        </p>
        <p className="text-small text-ink-2">{member.email}</p>
        {(update.isError || reset.isError) && <p className="mt-1 text-tiny text-danger-ink">{(update.error ?? reset.error)?.message}</p>}
      </td>
      <td className="py-3 pr-4">
        <Select
          aria-label={`Role for ${member.name}`}
          value={member.role}
          disabled={isMe || update.isPending}
          onChange={(e) => update.mutate({ role: e.target.value as UserRole })}
          className="h-8 text-small"
        >
          <option value="reviewer">Reviewer</option>
          <option value="admin">Admin</option>
        </Select>
      </td>
      <td className="py-3 pr-4">
        {member.is_active ? <Tag tone="ok">Active</Tag> : <Tag tone="muted">Deactivated</Tag>}
        <p className="mt-1 text-tiny text-ink-3">{member.last_login_at ? `Last in ${dateTime(member.last_login_at)}` : 'Never signed in'}</p>
      </td>
      <td className="py-3 text-right whitespace-nowrap">
        <Button size="sm" variant="ghost" loading={reset.isPending} onClick={() => reset.mutate()}>
          Reset password
        </Button>
        {!isMe && (
          <Button size="sm" variant="ghost" loading={update.isPending} onClick={() => update.mutate({ is_active: !member.is_active })}>
            {member.is_active ? 'Deactivate' : 'Reactivate'}
          </Button>
        )}
      </td>
    </tr>
  )
}

/** Who can sign in to this tenant, and the controls an admin has over them. */
export function TeamManager() {
  const { data: me } = useSession()
  const team = useQuery({ queryKey: teamKeys.all, queryFn: listTeam })
  const [issued, setIssued] = useState<PasswordIssued | null>(null)

  return (
    <div className="space-y-6">
      <Sheet title="Add a team member">
        <InviteForm onIssued={setIssued} />
      </Sheet>
      {issued && <OneTimePassword issued={issued} onDone={() => setIssued(null)} />}
      <Sheet title="Team" padded={false}>
        {team.isPending ? (
          <div className="px-5">
            <Loading label="Loading the team…" />
          </div>
        ) : team.isError ? (
          <div className="p-5">
            <ErrorNotice error={team.error} onRetry={() => void team.refetch()} />
          </div>
        ) : (
          <div className="overflow-x-auto px-5">
            <table className="w-full text-left text-small">
              <thead>
                <tr className="border-b-2 border-ink">
                  <th className="py-2 pr-4 font-semibold">Member</th>
                  <th className="py-2 pr-4 font-semibold">Role</th>
                  <th className="py-2 pr-4 font-semibold">Status</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {team.data.map((m) => (
                  <MemberRow key={m.id} member={m} isMe={m.id === me?.id} onIssued={setIssued} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </div>
  )
}
