// Conformance driver. All binding/clock overrides and keys are test-only.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"time"

	"licensebox.dev/client"
	"licensebox.dev/lease"
	"licensebox.dev/machine"
)

type request struct {
	Op, Product, Source, Token, Server, Directory, Binding, Module string
	RawID                                                          string `json:"raw_id"`
	Keys                                                           map[string]string
	Now                                                            int64
}

func errorCode(err error) string {
	var policy *client.PolicyError
	if errors.As(err, &policy) {
		return policy.Code
	}
	var module *client.ModuleError
	if errors.As(err, &module) {
		return "module_denied"
	}
	for _, item := range []struct {
		err  error
		code string
	}{
		{machine.ErrUnavailable, "identity_unavailable"}, {client.ErrMachineChanged, "machine_changed"},
		{client.ErrSeatTransferred, "seat_transferred"}, {client.ErrLocationDenied, "location_denied"},
		{client.ErrRevoked, "revoked"}, {client.ErrDenied, "denied"}, {client.ErrSignInExpired, "sign_in_expired"},
		{client.ErrNotSignedIn, "not_signed_in"}, {client.ErrOffline, "offline"}, {lease.ErrMalformed, "malformed"}, {lease.ErrVersion, "version"},
		{lease.ErrUnknownKey, "unknown_key"}, {lease.ErrBadSignature, "bad_signature"}, {lease.ErrExpired, "expired"},
	} {
		if errors.Is(err, item.err) {
			return item.code
		}
	}
	return "http_error"
}
func main() {
	var r request
	if err := json.NewDecoder(os.Stdin).Decode(&r); err != nil {
		panic(err)
	}
	keys := lease.Keys{}
	for kid, value := range r.Keys {
		key, err := lease.DecodeKey(value)
		if err != nil {
			panic(err)
		}
		keys[kid] = key
	}
	var value any
	var err error
	switch r.Op {
	case "derive":
		value, err = machine.Derive(r.Product, r.Source, r.RawID)
	case "native":
		value, err = machine.Native(r.Product)
	case "verify":
		value, err = lease.Check(r.Token, r.Product, keys, time.Unix(r.Now, 0))
	default:
		var c *client.Client
		c, err = client.New(client.Config{Product: r.Product, Keys: keys, Server: r.Server, Dir: r.Directory, Version: "conformance", Out: io.Discard, Now: func() time.Time { return time.Unix(r.Now, 0) }, MachineBinding: func() (machine.Binding, error) { return machine.Binding(r.Binding), nil }})
		if err == nil {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			switch r.Op {
			case "lease":
				value, err = c.Lease(ctx)
			case "require":
				if r.Module == "" {
					r.Module = "core"
				}
				value, err = c.Require(ctx, r.Module)
			case "repeat":
				value, err = c.Require(ctx, "core")
				if err == nil {
					value, err = c.Require(ctx, "core")
				}
			case "heartbeat", "heartbeat-repeat", "heartbeat-after-require":
				if r.Module == "" {
					r.Module = "core"
				}
				if r.Op == "heartbeat-after-require" {
					_, err = c.Require(ctx, r.Module)
				}
				if err == nil {
					value, err = c.Heartbeat(ctx, r.Module)
				}
				if err == nil && r.Op == "heartbeat-repeat" {
					value, err = c.Heartbeat(ctx, r.Module)
				}
			case "status":
				value, err = c.Status()
			case "sign_in":
				value, err = c.SignIn(ctx)
			case "logout":
				err = c.Logout()
			case "modules":
				value, err = c.Modules(ctx)
			case "request":
				value, err = c.RequestAccess(ctx, []string{"export"}, "café – test")
			case "requests":
				value, err = c.Requests(ctx)
			case "access-link":
				value, err = c.AccessLink(ctx)
			case "record":
				c.Record("export", true, 125*time.Millisecond)
				c.Record("export", false, 25*time.Millisecond)
			default:
				panic("unknown operation")
			}
		}
	}
	answer := map[string]any{"ok": err == nil, "value": value}
	if err != nil {
		answer["error"] = errorCode(err)
	}
	if err := json.NewEncoder(os.Stdout).Encode(answer); err != nil {
		panic(err)
	}
}
