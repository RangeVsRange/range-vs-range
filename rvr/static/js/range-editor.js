rank_select = function(_id) {
  $('#' + _id).toggleClass('r_sel');
  $('#sel_' + _id).val($('#' + _id).hasClass('r_sel'));
}
rank_set = function(_id, _val) {
  $('#' + _id).toggleClass('r_sel', _val);
  $('#sel_' + _id).val(_val);
}
rank_click = function(_id) {
  if (window.event.ctrlKey) {
    rank_select(_id);
    var _val = $('#' + _id).hasClass('r_sel')
    while (_id in $NEXT_MAP) {
      _id = $NEXT_MAP[_id]
      rank_set(_id, _val);
    }
  } else {
    rank_select(_id);
  }
};
suit_click = function(_id) {
  $('#' + _id).toggleClass('s_sel');
  $('#sel_' + _id).val($('#' + _id).hasClass('s_sel'));
};
select_all_rank = function(select) {
  $('.rank-button').toggleClass('r_sel', select);
  $('.r_h').val(select);
};
select_all_suit = function(select) {
  $('.suit-button').toggleClass('s_sel', select);
  $('.s_h').val(select);
};
post_to_parent = function(raise_total) {
  var doc = window.parent.document;
  var fold = doc.getElementById("fold");
  var passive = doc.getElementById("passive");
  var aggressive = doc.getElementById("aggressive");
  var total = doc.getElementById("total");
  fold.value = $RNG_FOLD;
  passive.value = $RNG_PASSIVE;
  aggressive.value = $RNG_AGGRESSIVE;
  if ($CAN_RAISE) {
    total.value = raise_total;
  }
  form = doc.getElementById("action");
  form.submit();
};
populate_parent = function() {
  var t;
  var r = $RNG_AGGRESSIVE;
  if ($CAN_RAISE && r != 'nothing') {
    t = parseInt($('#raise-total').val());
    if (isNaN(t)) {
      alert("You gotta enter a raise amount.");
      return false;
    }
    if (t < $MIN_RAISE) {
      alert("You gotta raise to at least " + $MIN_RAISE + ".");
      return false;
    }
    if (t > $MAX_RAISE) {
      alert("You can't raise to more than " + $MAX_RAISE + ".");
      return false;
    }
  }
  post_to_parent(t);
  return false;
};