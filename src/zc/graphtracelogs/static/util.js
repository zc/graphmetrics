dojo.provide('zc.util')

dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.TimeTextBox");
dojo.require('dijit.form.ValidationTextBox');
dojo.require("dijit.Tooltip");
dojo.require("dojo.date.stamp");

(function () {
//======================================================================

zc.util.tooltip = function (node, text) {
    new dijit.Tooltip({connectId: [node], label: text});
};

zc.util.TextUI = function (
  div, label, params, name, update, length, regex, tip) {
  var onChange = function(val) {
    params[name] = val;
    update();
  };
  var widget = new dijit.form.ValidationTextBox({
        value: params[name],
        maxLength: length,
        regExp: regex,
        style: 'width: ' + (length+3) + 'ch',
        onChange: onChange
    });
  dojo.place('<span> '+label+': </span>', div)
  dojo.connect(widget.domNode, 'onkeypress', function (e) {
      if (e.charCode == 0 && e.keyCode != 8)
            onChange(widget.getValue());
               });

  div.appendChild(widget.domNode);
  if (tip)
    zc.util.tooltip(widget.domNode, tip);

  this.update = function (settings) {
    widget.attr('value', settings[name] || null);
  };
};

var twodigits = function (i) {
    var result = i.toString();
    if (result.length < 2)
        result = '0' + i;
    return result;
};
var date2string = function (d) {
    if (d)
        return (d.getFullYear()
                + '-' + twodigits(d.getMonth()+1)
                + '-' + twodigits(d.getDate())
               );
    return undefined;
};
var string2date = function (s) {
    if (s)
        return dojo.date.stamp.fromISOString(s);
    return undefined;
};
var time2string = function (d) {
    if (d)
        return ('T'
                + d.getHours()
                + ':' + twodigits(d.getMinutes())
                + ':' + twodigits(d.getSeconds())
               );
    return undefined;
};
var string2time = function (s) {
    if (s) {
        var result = new Date();
        s = s.split('T')[1].split(':');
        result.setHours(s[0]);
        result.setMinutes(s[1]);
        result.setSeconds(s[2]);
        return result;
    }
    return undefined;
};

zc.util.DateTimeUI = function (div, params, name, update) {
    var changeDate = function(date) {
            params[name] = date2string(date);
            update();
    };
    var date_widget = new dijit.form.DateTextBox({
        value: string2date(params[name]),
        onChange: changeDate
    });
    dojo.connect(date_widget.domNode, 'onkeypress', function (e) {
        if (e.charCode == 0 && e.keyCode != 8)
            changeDate(date_widget.getValue());
    });
    div.appendChild(date_widget.domNode);
    dojo.style(div.lastChild, "width", "12ch");
    dojo.place('<span>T</span>', div)
    var changeTime = function(time) {
            params[name+'_time'] = time2string(time);
            update();
    };
    var time_widget = new dijit.form.TimeTextBox({
        value: string2time(params[name+'_time']),
        onChange: changeTime
    });
    dojo.connect(time_widget.domNode, 'onkeypress', function (e) {
        if (e.charCode == 0 && e.keyCode != 8)
            changeTime(time_widget.getValue());
    });
    div.appendChild(time_widget.domNode);
    dojo.style(div.lastChild, "width", "10ch");

    this.update = function (settings) {
        date_widget.attr('value', string2date(settings[name]) || null);
        time_widget.attr('value',
                         string2time(settings[name+'_time']) || null);
    };
};

zc.util.BoolUI = function (div, label, params, name, update) {
    var widget = new dijit.form.CheckBox({
        checked: params[name] == 'y' ? 'checked': undefined,
        onChange: function(val) {
            if (val)
                params[name] = 'y';
            else
                params[name] = undefined;
            update();
        }
    });
    dojo.place('<span> '+label+': </span>', div)
    div.appendChild(widget.domNode);

    this.update = function (settings) {
        widget.attr('checked',
                    settings[name] == 'y' ? 'checked': undefined);
    };
};

//======================================================================
})();
