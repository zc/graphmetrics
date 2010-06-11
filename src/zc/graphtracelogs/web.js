dojo.require("dijit.form.Button");
dojo.require("dijit.Menu");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dojo.data.ItemFileReadStore");

zc = function() {
    // var data = [{x: 1, y: 1}, {x: 2, y: 2}];

    // var update = function(value) {
    //     data[0] = {x: 1, y: 2};
    //     data[1] = {x: 2, y: 1};
    //     zc.chart1.updateSeries('Series 1', data);
    //     zc.chart1.render();
    // };
    var imgid = 0;
    var instances;

    var newChart = function(inst) {
        imgid ++;
        var div = dojo.create('div',{}, dojo.body())
        var params = {
            instance: inst,
            bust: 0
        };
        var img = dojo.create(
            'img', {id: 'img'+imgid,
                    src: 'show.png?'+dojo.objectToQuery(params)}, div);
        var update_img = function (ob) {
            if (ob != undefined)
                dojo.mixin(params, ob);
            params.bust++;
            img.src =  'show.png?'+dojo.objectToQuery(params);
        };
        var keep_refreshing = function () {
            if (params.end == null)
                update_img();
            setTimeout(keep_refreshing, 60000);
        };
        setTimeout(keep_refreshing, 60000);
        dojo.create('br', {}, div);
        div.appendChild(new dijit.form.Button({
            label: 'Reload',
            onClick: update_img
        }).domNode);
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date != null)
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                update_img({start: date});
            }
        }).domNode);
        dojo.place('<span> to </span>', div)
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date != null)
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                update_img({end: date});
            }
        }).domNode);
        dojo.place('<span> Log: </span>', div)
        div.appendChild(new dijit.form.CheckBox({
            onChange: function(val) {
                if (val)
                    params.log = 'y';
                else
                    params.log = 'n';
                update_img();
            }
        }).domNode);
        dojo.place('<span> Instance: </span>', div);
        div.appendChild(new dijit.form.FilteringSelect({
            searchAttr: 'label',
            store: new dojo.data.ItemFileReadStore({
                data: {identifier: 'id', label: 'label',
                       items: dojo.map(instances, function(inst) {
                           return {id: inst,
                                   label: replaceAll(inst, '__', ' ')
                                  };
                       })}
            }),
            onChange: function(val) { update_img({instance: val}); }
        }).domNode);
    };

    var replaceAll = function(str, orig, repl) {
        while (1) {
            var news = str.replace(orig, repl)
            if (news == str) return str;
            str = news;
        }
    };

    return {
        init: function()
        {
            dojo.xhrGet({
                url: 'get_instances.json',
                handleAs: 'json',
                load: function (data) {
                    instances = data.instances;
                    var menu = new dijit.Menu({
                        style: "display: none;"
                    });
                    for (var i=0; i < instances.length; i++) {
                        menu.addChild(new dijit.MenuItem({
                            label: replaceAll(instances[i], "__", " "),
                            onClick: dojo.partial(newChart, instances[i])
                        }));
                    }
                    dojo.body().appendChild(new dijit.form.ComboButton({
                        label: "New chart:",
                        dropDown: menu
                    }).domNode);
                },
                error: function (error) {alert(error)}
            });
        }
    }
}();

dojo.addOnLoad(zc.init);
