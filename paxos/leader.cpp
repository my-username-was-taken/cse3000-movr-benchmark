#include "paxos/leader.h"

#include <glog/logging.h>

#include "common/proto_utils.h"
#include "connection/sender.h"
#include "paxos/simulated_multi_paxos.h"

namespace slog {

using internal::Envelope;
using internal::Request;
using internal::Response;

Leader::Leader(SimulatedMultiPaxos& paxos, Members members, MachineId me)
    : paxos_(paxos), members_(members), me_(me), next_empty_slot_(0) {
  auto it = std::find(members.acceptors.begin(), members.acceptors.end(), me);
  if (it != members.acceptors.end()) {
    auto position_in_acceptors = it - members.acceptors.begin();
    is_elected_ = position_in_acceptors == kPaxosDefaultLeaderPosition;
    ballot_ = position_in_acceptors;
  } else {
    // When the current machine is not a voter of this paxos group, it
    // will always forward a proposal request to the initially elected
    // leader of the group (which would never change in this implementation
    // of paxos)
    is_elected_ = false;
  }
  elected_leader_ = members.acceptors[kPaxosDefaultLeaderPosition];
}

void Leader::HandleRequest(const Envelope& req) {
  switch (req.request().type_case()) {
    case Request::TypeCase::kPaxosPropose:
      // If elected as true leader, send accept request to the acceptors
      // Otherwise, forward the request to the true leader
      if (is_elected_) {
        StartNewInstance(req.request().paxos_propose().value());
      } else {
        paxos_.SendSameChannel(req, elected_leader_);
      }
      break;
    case Request::TypeCase::kPaxosCommit:
      ProcessCommitRequest(req.request().paxos_commit());
      break;
    default:
      break;
  }
}

void Leader::ProcessCommitRequest(const internal::PaxosCommitRequest& commit) {
  auto slot = commit.slot();

  // Report to the paxos user
  paxos_.OnCommit(slot, commit.value(), commit.leader());

  if (slot >= next_empty_slot_) {
    next_empty_slot_ = slot + 1;
  }
}

void Leader::HandleResponse(const Envelope& res) {
  if (res.response().has_paxos_accept()) {
    auto slot = res.response().paxos_accept().slot();
    auto it = instances_.find(slot);
    if (it == instances_.end()) {
      return;
    }
    auto& instance = it->second;
    ++instance.num_accepts;

    if (instance.num_accepts == static_cast<int>(members_.acceptors.size() / 2 + 1)) {
      auto env = paxos_.NewEnvelope();
      auto paxos_commit = env->mutable_request()->mutable_paxos_commit();
      paxos_commit->set_slot(slot);
      paxos_commit->set_value(instance.value);
      paxos_commit->set_leader(me_);
      paxos_.SendSameChannel(move(env), members_.learners);
    }
  } else if (res.response().has_paxos_commit()) {
    auto slot = res.response().paxos_accept().slot();
    auto it = instances_.find(slot);
    if (it == instances_.end()) {
      return;
    }
    auto& instance = it->second;
    ++instance.num_commits;
    if (instance.num_commits == static_cast<int>(members_.acceptors.size())) {
      instances_.erase(it);
    }
  }
}

void Leader::StartNewInstance(uint64_t value) {
  instances_.try_emplace(next_empty_slot_, ballot_, value);

  auto env = paxos_.NewEnvelope();
  auto paxos_accept = env->mutable_request()->mutable_paxos_accept();
  paxos_accept->set_ballot(ballot_);
  paxos_accept->set_slot(next_empty_slot_);
  paxos_accept->set_value(value);
  next_empty_slot_++;

  paxos_.SendSameChannel(move(env), members_.acceptors);
}

}  // namespace slog