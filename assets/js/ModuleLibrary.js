import PropTypes from 'prop-types';
import React from 'react';
import { sortable } from 'react-sortable';
import ModuleCategory from './ModuleCategory';
import ImportModuleFromGitHub from './ImportModuleFromGitHub';
import Module from './Module';
import ModuleSearch from './ModuleSearch';


var SortableCategories = sortable(ModuleCategory);

class CategoriesList extends React.Component {
  render() {
    var hasModules = (!!this.props.workflow.wf_modules && !!this.props.workflow.wf_modules.length);

    var listItems = this.props.data.map(function (item, i) {
      return (
        <SortableCategories
          key={item.key}
          category={item.props.category}
          items={this.props}
          sortId={item.key}
          outline="list"
          childProps={{
            'data-name': item.key, // category
            'data-modules': item.props.modules, // modules in this category
            'collapsed': !(item.key == "Add data" && !hasModules), // Have "Add data" category open when no modules in workflow
          }}
        />
      );
    }, this);
    return (
      <div className="list">{listItems}</div>
    );
  }
}

/**
 * Contains the Module Library. The Module Library is effectively the place
 * that allows users to browse all the modules in the system that are
 * available to them. Therefore, the server should only send through the
 * modules the users are entitled to, and this class will render those modules
 * accordingly, and allow users to add them to workflows.
 *
 * Note: the current implementation mandates that this library appears vis-à-vis
 * the workflow, and is not an independent component. Perhaps, at some point, it
 * should be, so that newcomers to the system can get an idea as to the modules
 * that are supported – both, those created by us and those created by third
 * parties.
 */
export default class ModuleLibrary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      libraryOpen: true,
      items: [],
    };
    this.addModule = this.props.addModule.bind(this);
    this.workflow = this.props.workflow;
    this.toggleLibrary = this.toggleLibrary.bind(this);
  }

  /**
   * Queries server for all the available modules for the given credentials.
   * The response that's returned should be a list, where each item has the
   * following properties:
   * - name (e.g. "Paste CSV")
   * - id (e.g. 8)
   * - category (e.g. "Sources")
   * - description (e.g. "Allows users to copy in a CSV from an external source.")
   *
   * Additionally, these properties are optional (and mostly used by modules
   * imported from GitHub, i.e. not the core modules):
   * - icon
   * - source
   * - author
   * - version
   */
  componentWillMount() {
    fetch('/api/modules/', { credentials: 'include' })
      .then(response => response.json())
      .then(json => {
        // Sort modules – first by category, then by name
        json.sort((a, b) => {
          if (a.category > b.category) {
            return 1;
          } else if (a.category < b.category) {
            return -1;
          } else if (a.name > b.name) {
            return 1;
          } else if (a.name < b.name) {
            return -1;
          } else {
            return 0;
          }
        });
        this.setState({ items: json });
      })
      .catch((error) => {
        console.log('Unable to retrieve modules to construct the Module Library.', error);
      });
  }

  itemClick(event) {
    this.props.addModule(event.target.id);
  }

  updated(updated) {
    this.componentWillMount() // dummy update to force a re-render.
  }

  toggleLibrary() {
    this.setState({ libraryOpen: !this.state.libraryOpen });
  }


  /**
   * Renders the Module Library, i.e. a collection of <Module Category>,
   * which in turn is a collection of <Module>.
   *
   * This is sorted by the Category name, but we might want to define a
   * better sorting order.
   */
  render() {
    // This assumes that the items are already sorted by category,
    // which does happen in {code: componentDidMount}. So, if someone
    // changes that, there is a good chance that this will result in
    // unexpected behaviour.
    let modules = this.state.items;
    var previousCategory = null;
    var modulesByCategory = [];
    var categories = [];
    for (let item of modules) { // Yes, for...of is ES6 syntax, and yes, it's gross.
      let module = <Module
        icon={item.icon}
        key={item.name}
        description={item.description}
        category={item.category}
        author={item.author}
        id={item.id}
        addModule={this.props.addModule}
        workflow={this.props.workflow}
      />;

      if (previousCategory == null) {
        previousCategory = item.category;
      } else if (previousCategory !== item.category) {
        // We should only create the ModuleCategory once we have all modules
        // for given category.
        let moduleCategory = <ModuleCategory
          key={previousCategory}
          modules={modulesByCategory}
          />;
        categories.push(moduleCategory);
        modulesByCategory = [];
        previousCategory = item.category;
      }
      modulesByCategory.push(module);
    }


    // the last item / category
    let moduleCategory =  <ModuleCategory
                            key={previousCategory}
                            modules={modulesByCategory}
                          />;
    categories.push(moduleCategory);

    let visible = <div className='module-library-open'>
                    <div className='library-nav-bar'>
                      <div className='d-flex align-items-center flex-row mb-4'>
                        <a href="/workflows" className="logo"><img src="/static/images/logo.png" width="20"/></a>
                        <span className='logo-2 ml-3 t-vl-gray '>Workbench</span>
                        <div className='icon-sort-left-vl-gray ml-auto mt-1 close-open-toggle'onClick={this.toggleLibrary}></div>
                      </div>
                      <ModuleSearch addModule={this.props.addModule}
                                      items={this.state.items}
                                      workflow={this.workflow}/>
                    </div>
                      <div className=''>
                        <CategoriesList
                          data={categories}
                          workflow={this.props.workflow}
                        />
                    </div>
                    <ImportModuleFromGitHub moduleLibrary={this}/>
                  </div>

    let collapsed = <div className='module-library-collapsed'>
                      <div className="expand-lib">
                        <div className="expand-lib-button d-flex">
                          <div className="logo" onClick={this.toggleLibrary}><img src="/static/images/logo.png" width="20"/></div>
                          <div className='icon-sort-right-vl-gray ml-auto ml-3 mt-2 close-open-toggle' onClick={this.toggleLibrary}></div>
                        </div>
                      </div>
                    </div>
    let library = (this.state.libraryOpen) ? visible : collapsed

    return (
      <div className=''>
        {library}
      </div>
    );
  }
}

ModuleLibrary.propTypes = {
  addModule: PropTypes.func.isRequired,
  workflow:  PropTypes.object.isRequired,
  api:       PropTypes.object.isRequired,
};
